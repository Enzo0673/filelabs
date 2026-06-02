"""
CompressIt - Serveur FastAPI local
Lance avec : py main.py  (ou  uvicorn main:app --reload)
Accès : http://localhost:8000
"""

import os
import re
import sys
import uuid
import zipfile
import hashlib
import logging
import mimetypes
import threading
import webbrowser
import time
import shutil
import subprocess
import asyncio
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import StreamingResponse
logger = logging.getLogger(__name__)
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from compressors.image import compress_image
from compressors.pdf import compress_pdf
from compressors.video import compress_video, trim_video, resize_video, merge_videos, add_text_video, FFMPEG_AVAILABLE as _FFMPEG_AVAILABLE
from compressors.archive import compress_archive
from compressors.pdf_tools import (
    merge_pdfs, split_pdf, pdf_to_jpg, jpg_to_pdf,
    rotate_pdf, rotate_pdf_map, watermark_pdf, add_page_numbers,
    delete_pages, unlock_pdf, protect_pdf, repair_pdf, extract_pdf_text,
)
from compressors.image_tools import resize_image, convert_image, crop_image, rotate_image

# Résolution des chemins compatible PyInstaller (--onefile extrait dans sys._MEIPASS)
if getattr(sys, "frozen", False):
    # Exécutable PyInstaller : fichiers embarqués dans le bundle
    _BUNDLE_DIR = Path(sys._MEIPASS)
    # Uploads/outputs à côté de l'exe, pas dans le temp
    _EXE_DIR = Path(sys.executable).parent
else:
    _BUNDLE_DIR = Path(__file__).parent
    _EXE_DIR = Path(__file__).parent

# Hash de version pour invalider le cache SW automatiquement à chaque déploiement
def _compute_static_hash() -> str:
    h = hashlib.md5()
    static = _BUNDLE_DIR / "static"
    for f in sorted(static.rglob("*")):
        if f.is_file() and not f.name.endswith(".pyc"):
            try:
                h.update(f.read_bytes())
            except Exception:
                pass
    return h.hexdigest()[:8]

_STATIC_VERSION = _compute_static_hash()

BASE_DIR = _BUNDLE_DIR
UPLOAD_DIR = _EXE_DIR / "uploads"
OUTPUT_DIR = _EXE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
# Permissions restrictives (Linux/Mac uniquement)
if os.name != "nt":
    import stat
    UPLOAD_DIR.chmod(stat.S_IRWXU)
    OUTPUT_DIR.chmod(stat.S_IRWXU)

# Limites de taille d'upload par type (en octets)
MAX_SIZE = {
    "image":   32 * 1024 * 1024,   # 32 MB
    "pdf":     32 * 1024 * 1024,   # 32 MB
    "video":  500 * 1024 * 1024,   # 500 MB
    "archive": 200 * 1024 * 1024,  # 200 MB
}
MAX_SIZE_DEFAULT = 200 * 1024 * 1024

# Détection LibreOffice pour la conversion Word/Excel → PDF
def _find_libreoffice() -> str | None:
    candidates = [
        "libreoffice", "soffice",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/usr/bin/libreoffice", "/usr/bin/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for c in candidates:
        if shutil.which(c) or Path(c).exists():
            return c
    return None

_LIBREOFFICE = _find_libreoffice()
OFFICE_AVAILABLE = _LIBREOFFICE is not None

# TTL des fichiers output (secondes)
OUTPUT_TTL = 3600  # 1 heure
_APP_START = time.time()


def _dir_size_mb(path: Path) -> float:
    try:
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return round(total / (1024 * 1024), 2)
    except Exception:
        return 0.0


def _cleanup_outputs():
    """Supprime les fichiers output de plus d'1h. Tourne en boucle toutes les 15min."""
    while True:
        time.sleep(900)
        cutoff = time.time() - OUTPUT_TTL
        for f in OUTPUT_DIR.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
            except Exception:
                pass

app = FastAPI(title="CompressIt", version="1.0.0")

# Rate limiting — actif uniquement sur la version en ligne (Render injecte la var RENDER)
_IS_LOCAL = os.environ.get("RENDER") is None
_rate_buckets: dict = {}  # {ip: [timestamp, ...]}
_RATE_LIMIT = 20          # requêtes max
_RATE_WINDOW = 60         # par fenêtre de 60s
_RATE_LAST_PURGE = time.time()
_PROCESSING_PATHS = ("/compress", "/pdf/", "/image/", "/video/", "/download/")

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    global _RATE_LAST_PURGE
    if not _IS_LOCAL and any(request.url.path.startswith(p) for p in _PROCESSING_PATHS):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        bucket = [t for t in _rate_buckets.get(ip, []) if now - t < _RATE_WINDOW]
        if len(bucket) >= _RATE_LIMIT:
            from starlette.responses import JSONResponse
            return JSONResponse({"detail": "Trop de requêtes — réessayez dans une minute."}, status_code=429)
        bucket.append(now)
        _rate_buckets[ip] = bucket
        # Purge des IPs inactives toutes les 5 minutes pour éviter la fuite mémoire
        if now - _RATE_LAST_PURGE > 300:
            cutoff = now - _RATE_WINDOW
            for k in list(_rate_buckets.keys()):
                if not _rate_buckets[k] or max(_rate_buckets[k]) < cutoff:
                    del _rate_buckets[k]
            _RATE_LAST_PURGE = now
    return await call_next(request)

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if not _IS_LOCAL:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        not_found = BASE_DIR / "static" / "404.html"
        if not_found.exists():
            return HTMLResponse(content=not_found.read_text(encoding="utf-8"), status_code=404)
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

# Lancer le nettoyage automatique en arrière-plan
threading.Thread(target=_cleanup_outputs, daemon=True).start()

# Types MIME → catégorie
MIME_MAP = {
    "image": ["image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp", "image/tiff"],
    "pdf":   ["application/pdf"],
    "video": ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/x-matroska"],
    "archive": [
        "application/zip", "application/x-7z-compressed", "application/x-rar-compressed",
        "application/gzip", "application/x-tar", "application/x-bzip2",
        "application/octet-stream",  # fallback pour zstd/lz4
    ],
}

_UID_RE = re.compile(r'^[a-f0-9]{32}$')
_VALID_CODECS   = {"h264", "h265", "vp9"}
_VALID_PRESETS  = {"ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"}
_VALID_HEIGHTS  = {None, 480, 720, 1080}
MAX_MERGE_FILES = 50

# Progression vidéo — partagé entre thread compress et endpoint SSE
_video_progress: dict = {}  # {uid: float 0-100}


def _validate_uid(uid: str):
    if not _UID_RE.match(uid):
        raise HTTPException(status_code=400, detail="UID invalide")


async def _save_upload(file: UploadFile, dest: Path, max_bytes: int = MAX_SIZE_DEFAULT):
    """Écrit un UploadFile sur disque en chunks async, lève HTTPException si trop gros."""
    size = 0
    try:
        with open(dest, "wb") as f_out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Fichier trop volumineux (max {max_bytes // 1024 // 1024} MB)"
                    )
                f_out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        dest.unlink(missing_ok=True)
        logger.error("Erreur écriture upload: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de la réception du fichier")


def detect_type(filename: str, mime: str) -> str:
    ext = Path(filename).suffix.lower()
    ext_map = {
        ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image",
        ".gif": "image", ".bmp": "image", ".tiff": "image", ".tif": "image",
        ".pdf": "pdf",
        ".mp4": "video", ".mov": "video", ".avi": "video", ".mkv": "video",
        ".webm": "video", ".m4v": "video", ".flv": "video",
        ".zip": "archive", ".7z": "archive", ".rar": "archive",
        ".gz": "archive", ".tar": "archive", ".bz2": "archive",
        ".zst": "archive", ".lz4": "archive", ".xz": "archive",
    }
    if ext in ext_map:
        return ext_map[ext]
    for cat, mimes in MIME_MAP.items():
        if mime in mimes:
            return cat
    return "archive"  # fallback générique

@app.get("/manifest.json")
async def manifest():
    path = BASE_DIR / "static" / "manifest.json"
    return FileResponse(path=path, media_type="application/manifest+json")


@app.get("/sitemap.xml")
async def sitemap():
    path = BASE_DIR / "static" / "sitemap.xml"
    return FileResponse(path=path, media_type="application/xml")


@app.get("/robots.txt")
async def robots():
    path = BASE_DIR / "static" / "robots.txt"
    return FileResponse(path=path, media_type="text/plain")


@app.get("/favicon.ico")
async def favicon():
    path = BASE_DIR / "static" / "favicon.ico"
    return FileResponse(path=path, media_type="image/x-icon")


@app.get("/service-worker.js")
async def service_worker():
    sw_path = BASE_DIR / "static" / "service-worker.js"
    content = sw_path.read_text(encoding="utf-8")
    content = re.sub(r"compressit-v\d+", f"compressit-{_STATIC_VERSION}", content)
    from fastapi.responses import Response
    return Response(content=content, media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})


@app.get("/static/service-worker.js")
async def service_worker_static():
    sw_path = BASE_DIR / "static" / "service-worker.js"
    content = sw_path.read_text(encoding="utf-8")
    content = re.sub(r"compressit-v\d+", f"compressit-{_STATIC_VERSION}", content)
    from fastapi.responses import Response
    return Response(content=content, media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})


@app.get("/privacy", response_class=HTMLResponse)
async def privacy():
    path = BASE_DIR / "static" / "privacy.html"
    return HTMLResponse(content=path.read_text(encoding="utf-8"))


@app.get("/tool/{tool_name}", response_class=HTMLResponse)
async def tool_page(tool_name: str):
    tools_dir = (BASE_DIR / "static" / "tools").resolve()
    tool_path = BASE_DIR / "static" / "tools" / f"{tool_name}.html"
    # Protection path traversal
    try:
        tool_path.resolve().relative_to(tools_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Nom d'outil invalide")
    if not tool_path.exists():
        not_found = BASE_DIR / "static" / "404.html"
        return HTMLResponse(content=not_found.read_text(encoding="utf-8"), status_code=404)
    return HTMLResponse(content=tool_path.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = BASE_DIR / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

@app.post("/compress")
async def compress(
    file: UploadFile = File(...),
    level: str = Form("standard"),        # light | standard | aggressive
    job_id: str = Form(None),             # ID client pour SSE progression vidéo
    # Options expert image
    img_quality: int = Form(None),        # 1-100
    img_format: str = Form(None),         # jpeg | png | webp
    img_max_width: int = Form(None),      # px
    # Options expert vidéo
    vid_crf: int = Form(None),            # 0-51 (H.264)
    vid_codec: str = Form("h264"),        # h264 | h265 | vp9
    vid_preset: str = Form("medium"),     # ultrafast...veryslow
    vid_max_height: int = Form(None),     # 480 | 720 | 1080
    # Options expert PDF
    pdf_dpi: int = Form(None),            # DPI des images internes
    pdf_remove_metadata: bool = Form(True),
    # Options expert archive
    arc_algo: str = Form(None),           # zstd | lzma | gzip | brotli
    arc_level: int = Form(None),          # niveau algorithme natif
):
    # Validation des paramètres
    if level not in {"light", "standard", "aggressive"}:
        raise HTTPException(status_code=400, detail="Niveau de compression invalide")
    if vid_codec not in _VALID_CODECS:
        raise HTTPException(status_code=400, detail="Codec vidéo invalide")
    if vid_preset not in _VALID_PRESETS:
        raise HTTPException(status_code=400, detail="Preset vidéo invalide")
    if vid_crf is not None and not (0 <= vid_crf <= 51):
        raise HTTPException(status_code=400, detail="CRF doit être entre 0 et 51")
    if vid_max_height is not None and vid_max_height not in _VALID_HEIGHTS:
        raise HTTPException(status_code=400, detail="Hauteur vidéo invalide (480, 720, 1080)")
    if pdf_dpi is not None and not (30 <= pdf_dpi <= 300):
        raise HTTPException(status_code=400, detail="DPI doit être entre 30 et 300")
    if img_quality is not None and not (1 <= img_quality <= 100):
        raise HTTPException(status_code=400, detail="Qualité image doit être entre 1 et 100")
    if img_max_width is not None and not (1 <= img_max_width <= 10000):
        raise HTTPException(status_code=400, detail="Largeur max doit être entre 1 et 10000")
    # Sauvegarder le fichier uploadé
    uid = uuid.uuid4().hex
    original_ext = Path(file.filename).suffix.lower()
    input_path = UPLOAD_DIR / f"{uid}_input{original_ext}"

    mime = file.content_type or mimetypes.guess_type(file.filename)[0] or ""
    file_type = detect_type(file.filename, mime)
    max_bytes = MAX_SIZE.get(file_type, MAX_SIZE_DEFAULT)

    # Écriture async chunk par chunk + vérification taille
    size = 0
    try:
        with open(input_path, "wb") as f_out:
            while chunk := await file.read(1024 * 1024):  # 1 MB chunks
                size += len(chunk)
                if size > max_bytes:
                    input_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Fichier trop volumineux (max {max_bytes // 1024 // 1024} MB pour ce type)"
                    )
                f_out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        input_path.unlink(missing_ok=True)
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")

    original_size = input_path.stat().st_size

    output_path = OUTPUT_DIR / f"{uid}_output{original_ext}"

    try:
        if file_type == "image":
            output_path = compress_image(
                input_path, output_path, level,
                quality=img_quality, output_format=img_format, max_width=img_max_width
            )
        elif file_type == "pdf":
            output_path = compress_pdf(
                input_path, output_path, level,
                dpi=pdf_dpi, remove_metadata=pdf_remove_metadata
            )
        elif file_type == "video":
            # Utiliser job_id fourni par le client pour la progression SSE
            progress_key = job_id if (job_id and _UID_RE.match(job_id)) else uid
            _video_progress[progress_key] = 0.0

            def _progress_cb(pct: float):
                _video_progress[progress_key] = pct

            loop = asyncio.get_event_loop()
            output_path = await loop.run_in_executor(
                None,
                lambda: compress_video(
                    input_path, output_path, level,
                    crf=vid_crf, codec=vid_codec, preset=vid_preset,
                    max_height=vid_max_height, on_progress=_progress_cb,
                )
            )
            _video_progress.pop(progress_key, None)
        else:
            output_path = compress_archive(
                input_path, output_path, level,
                algo=arc_algo, algo_level=arc_level
            )

        compressed_size = output_path.stat().st_size
        gain_pct = round((1 - compressed_size / original_size) * 100, 1)
        output_filename = Path(file.filename).stem + "_compressed" + output_path.suffix

        return {
            "success": True,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "gain_pct": gain_pct,
            "output_filename": output_filename,
            "download_id": uid,
            "file_type": file_type,
        }

    except Exception as e:
        input_path.unlink(missing_ok=True)
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


@app.get("/download/{uid}")
async def download(uid: str):
    _validate_uid(uid)
    matches = list(OUTPUT_DIR.glob(f"{uid}_output*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Fichier introuvable ou expiré")
    output_path = matches[0]
    # Vérifier que le chemin résolu reste dans OUTPUT_DIR (path traversal)
    try:
        output_path.resolve().relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Accès refusé")
    mime_type, _ = mimetypes.guess_type(str(output_path))
    if not mime_type:
        mime_type = "application/octet-stream"
    return FileResponse(
        path=output_path,
        filename=output_path.name,
        media_type=mime_type,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@app.get("/compress/progress/{uid}")
async def compress_progress(uid: str):
    """SSE endpoint — streame la progression FFmpeg pour un job vidéo."""
    _validate_uid(uid)

    async def event_stream():
        sent_done = False
        while True:
            pct = _video_progress.get(uid)
            if pct is None:
                if not sent_done:
                    yield "data: 100\n\n"
                break
            yield f"data: {pct:.1f}\n\n"
            if pct >= 100.0:
                sent_done = True
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )



# ---- Compression par lot ----
MAX_BATCH_FILES = 20

@app.post("/compress/batch")
async def compress_batch(
    files: List[UploadFile] = File(...),
    level: str = Form("standard"),
):
    if not files or len(files) > MAX_BATCH_FILES:
        raise HTTPException(status_code=400, detail=f"1 à {MAX_BATCH_FILES} fichiers requis")
    if level not in {"light", "standard", "aggressive"}:
        raise HTTPException(status_code=400, detail="Niveau de compression invalide")

    batch_uid = uuid.uuid4().hex
    input_paths = []
    output_paths = []

    try:
        for i, f in enumerate(files):
            uid = uuid.uuid4().hex
            mime = f.content_type or mimetypes.guess_type(f.filename)[0] or ""
            file_type = detect_type(f.filename, mime)
            max_bytes = MAX_SIZE.get(file_type, MAX_SIZE_DEFAULT)
            ext = Path(f.filename).suffix.lower()
            in_path = UPLOAD_DIR / f"{uid}_input{ext}"
            out_path = OUTPUT_DIR / f"{uid}_output{ext}"
            await _save_upload(f, in_path, max_bytes)
            input_paths.append(in_path)

            if file_type == "image":
                out_path = compress_image(in_path, out_path, level)
            elif file_type == "pdf":
                out_path = compress_pdf(in_path, out_path, level)
            elif file_type == "video":
                loop = asyncio.get_event_loop()
                captured_in, captured_out = in_path, out_path
                out_path = await loop.run_in_executor(
                    None, lambda ip=captured_in, op=captured_out: compress_video(ip, op, level)
                )
            else:
                out_path = compress_archive(in_path, out_path, level)
            output_paths.append(out_path)

        zip_path = OUTPUT_DIR / f"{batch_uid}_output.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for i, (orig_file, out_p) in enumerate(zip(files, output_paths)):
                stem = Path(orig_file.filename).stem
                arcname = f"{i+1}_{stem}_compressed{out_p.suffix}"
                zf.write(out_p, arcname)

        return {
            "success": True,
            "download_id": batch_uid,
            "output_filename": "batch_compressed.zip",
            "count": len(files),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement")
    finally:
        for p in input_paths:
            p.unlink(missing_ok=True)
        for p in output_paths:
            p.unlink(missing_ok=True)


# ---- Fusionner PDF ----
@app.post("/pdf/merge")
async def pdf_merge(files: List[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Au moins 2 fichiers requis")
    if len(files) > MAX_MERGE_FILES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_MERGE_FILES} fichiers")
    uid = uuid.uuid4().hex
    input_paths = []
    try:
        for i, f in enumerate(files):
            p = UPLOAD_DIR / f"{uid}_input_{i}.pdf"
            await _save_upload(f, p, MAX_SIZE["pdf"])
            input_paths.append(p)
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        result = merge_pdfs(input_paths, output_path)
        return {"success": True, "download_id": uid, "output_filename": "merged.pdf"}
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        for p in input_paths:
            p.unlink(missing_ok=True)


# ---- Diviser PDF ----
@app.post("/pdf/split")
async def pdf_split(
    file: UploadFile = File(...),
    ranges: str = Form(None),
):
    if ranges is not None and len(ranges) > 500:
        raise HTTPException(status_code=400, detail="Paramètre ranges trop long")
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        await _save_upload(file, input_path, MAX_SIZE["pdf"])
        output_dir = OUTPUT_DIR / uid
        result = split_pdf(input_path, output_dir, ranges)
        output_path = OUTPUT_DIR / f"{uid}_output.zip"
        result.rename(output_path)
        return {"success": True, "download_id": uid, "output_filename": "split_result.zip"}
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


# ---- PDF vers JPG ----
@app.post("/pdf/to-jpg")
async def pdf_to_jpg_route(
    file: UploadFile = File(...),
    dpi: int = Form(150),
):
    if not 50 <= dpi <= 600:
        raise HTTPException(status_code=400, detail="DPI doit être entre 50 et 600")
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        await _save_upload(file, input_path, MAX_SIZE["pdf"])
        output_path = OUTPUT_DIR / f"{uid}_output.zip"
        pdf_to_jpg(input_path, output_path, dpi=dpi)
        return {"success": True, "download_id": uid, "output_filename": "pages.zip"}
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


# ---- JPG vers PDF ----
@app.post("/pdf/from-jpg")
async def jpg_to_pdf_route(files: List[UploadFile] = File(...)):
    uid = uuid.uuid4().hex
    input_paths = []
    try:
        for i, f in enumerate(files):
            ext = Path(f.filename).suffix.lower() or ".jpg"
            p = UPLOAD_DIR / f"{uid}_input_{i}{ext}"
            await _save_upload(f, p, MAX_SIZE["image"])
            input_paths.append(p)
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        jpg_to_pdf(input_paths, output_path)
        return {"success": True, "download_id": uid, "output_filename": "images.pdf"}
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        for p in input_paths:
            p.unlink(missing_ok=True)


# ---- Rotation PDF ----
@app.post("/pdf/rotate")
async def pdf_rotate(
    file: UploadFile = File(...),
    angle: int = Form(None),
    pages: str = Form(None),
    rotation_map: str = Form(None),
):
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        await _save_upload(file, input_path, MAX_SIZE["pdf"])
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        if rotation_map:
            rotate_pdf_map(input_path, output_path, rotation_map)
        else:
            rotate_pdf(input_path, output_path, angle=angle or 90, pages=pages or "all")
        return {"success": True, "download_id": uid, "output_filename": "rotated.pdf"}
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Filigrane PDF ----
@app.post("/pdf/watermark")
async def pdf_watermark(
    file: UploadFile = File(...),
    text: str = Form("CONFIDENTIEL"),
    opacity: float = Form(0.3),
    position: str = Form("diagonal"),
    color: str = Form("gray"),
):
    if len(text) > 200:
        raise HTTPException(status_code=400, detail="Texte trop long (200 caractères max)")
    if not 0.0 <= opacity <= 1.0:
        raise HTTPException(status_code=400, detail="Opacity doit être entre 0.0 et 1.0")
    _VALID_POSITIONS = {"diagonal", "horizontal", "top", "bottom"}
    if position not in _VALID_POSITIONS:
        raise HTTPException(status_code=400, detail="Position invalide")
    _VALID_COLORS = {"gray", "black", "red", "blue"}
    if color not in _VALID_COLORS:
        raise HTTPException(status_code=400, detail="Couleur invalide")
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        await _save_upload(file, input_path, MAX_SIZE["pdf"])
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        watermark_pdf(input_path, output_path, text=text, opacity=opacity, position=position, color=color)
        return {"success": True, "download_id": uid, "output_filename": "watermarked.pdf"}
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Numéroter pages ----
@app.post("/pdf/page-numbers")
async def pdf_page_numbers(
    file: UploadFile = File(...),
    position: str = Form("bottom-center"),
):
    _VALID_PAGE_NUMBER_POSITIONS = {"bottom-center", "bottom-left", "bottom-right", "top-center", "top-left", "top-right"}
    if position not in _VALID_PAGE_NUMBER_POSITIONS:
        raise HTTPException(status_code=400, detail="Position invalide")
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        await _save_upload(file, input_path, MAX_SIZE["pdf"])
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        add_page_numbers(input_path, output_path, position=position)
        return {"success": True, "download_id": uid, "output_filename": "numbered.pdf"}
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Supprimer pages ----
@app.post("/pdf/delete-pages")
async def pdf_delete_pages(
    file: UploadFile = File(...),
    pages: str = Form(...),
):
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        await _save_upload(file, input_path, MAX_SIZE["pdf"])
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        delete_pages(input_path, output_path, pages_to_delete=pages)
        return {"success": True, "download_id": uid, "output_filename": "result.pdf"}
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Déverrouiller PDF ----
@app.post("/pdf/unlock")
async def pdf_unlock(
    file: UploadFile = File(...),
    password: str = Form(""),
):
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        await _save_upload(file, input_path, MAX_SIZE["pdf"])
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        unlock_pdf(input_path, output_path, password=password)
        return {"success": True, "download_id": uid, "output_filename": "unlocked.pdf"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Mot de passe incorrect")
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Protéger PDF ----
@app.post("/pdf/protect")
async def pdf_protect(
    file: UploadFile = File(...),
    password: str = Form(...),
):
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        await _save_upload(file, input_path, MAX_SIZE["pdf"])
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        protect_pdf(input_path, output_path, password=password)
        return {"success": True, "download_id": uid, "output_filename": "protected.pdf"}
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Réparer PDF ----
@app.post("/pdf/repair")
async def pdf_repair(
    file: UploadFile = File(...),
    remove_blank_pages: bool = Form(False),
    flatten_annotations: bool = Form(False),
):
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        await _save_upload(file, input_path, MAX_SIZE["pdf"])
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        result = repair_pdf(
            input_path, output_path,
            remove_blank_pages=remove_blank_pages,
            flatten_annotations=flatten_annotations,
        )
        return {
            "success": True,
            "download_id": uid,
            "output_filename": "repaired.pdf",
            "removed_pages": result["removed_pages"],
            "pages_remaining": result["pages_remaining"],
        }
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Extraire texte PDF ----
@app.post("/pdf/extract-text")
async def pdf_extract_text(file: UploadFile = File(...)):
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        await _save_upload(file, input_path, MAX_SIZE["pdf"])
        result = extract_pdf_text(str(input_path))
        return result
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de l'extraction du texte")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Word / Excel / PowerPoint → PDF ----
@app.get("/office/status")
async def office_status():
    return {"available": OFFICE_AVAILABLE}

@app.post("/office/to-pdf")
async def office_to_pdf(file: UploadFile = File(...)):
    if not OFFICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="LibreOffice non disponible sur ce serveur.")
    ext = Path(file.filename or "file").suffix.lower()
    allowed = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp"}
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Format non supporté.")
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    output_dir = OUTPUT_DIR / uid
    try:
        await _save_upload(file, input_path, MAX_SIZE["pdf"])
        output_dir.mkdir(exist_ok=True)
        result = subprocess.run(
            [_LIBREOFFICE, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(input_path)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise ValueError(result.stderr or "Échec de la conversion")
        pdf_files = list(output_dir.glob("*.pdf"))
        if not pdf_files:
            raise ValueError("Aucun PDF généré")
        output_path = pdf_files[0]
        final_path = OUTPUT_DIR / f"{uid}_output.pdf"
        output_path.rename(final_path)
        stem = Path(file.filename).stem
        return {
            "success": True,
            "download_id": uid,
            "output_filename": stem + ".pdf",
        }
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de la conversion")
    finally:
        input_path.unlink(missing_ok=True)
        if output_dir.exists():
            import shutil as _shutil
            _shutil.rmtree(output_dir, ignore_errors=True)


# ---- Découper vidéo ----
@app.post("/video/trim")
async def video_trim(
    file: UploadFile = File(...),
    start: float = Form(0.0),
    end: float = Form(...),
):
    uid = uuid.uuid4().hex
    ext = Path(file.filename or "video.mp4").suffix.lower() or ".mp4"
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    output_path = OUTPUT_DIR / f"{uid}_output{ext}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["video"])
        if start < 0 or end <= start:
            raise HTTPException(status_code=400, detail="Timestamps invalides.")
        result = trim_video(input_path, output_path, start=start, end=end)
        stem = Path(file.filename).stem
        return {"success": True, "download_id": uid, "output_filename": stem + "_trimmed" + result.suffix}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du découpage")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Redimensionner vidéo ----
@app.post("/video/resize")
async def video_resize_route(
    file: UploadFile = File(...),
    width: int = Form(None),
    height: int = Form(None),
):
    uid = uuid.uuid4().hex
    ext = Path(file.filename or "video.mp4").suffix.lower() or ".mp4"
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    output_path = OUTPUT_DIR / f"{uid}_output{ext}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["video"])
        if not width and not height:
            raise HTTPException(status_code=400, detail="Au moins une dimension requise.")
        if width and (width < 1 or width > 7680):
            raise HTTPException(status_code=400, detail="Largeur invalide.")
        if height and (height < 1 or height > 4320):
            raise HTTPException(status_code=400, detail="Hauteur invalide.")
        result = resize_video(input_path, output_path, width=width, height=height)
        stem = Path(file.filename).stem
        return {"success": True, "download_id": uid, "output_filename": stem + "_resized" + result.suffix}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du redimensionnement")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Fusionner vidéos ----
@app.post("/video/merge")
async def video_merge(files: List[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Au moins 2 vidéos requises.")
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 vidéos.")
    uid = uuid.uuid4().hex
    input_paths = []
    try:
        for i, f in enumerate(files):
            ext = Path(f.filename or "video.mp4").suffix.lower() or ".mp4"
            p = UPLOAD_DIR / f"{uid}_input_{i}{ext}"
            await _save_upload(f, p, MAX_SIZE["video"])
            input_paths.append(p)
        output_path = OUTPUT_DIR / f"{uid}_output.mp4"
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: merge_videos(input_paths, output_path)
        )
        return {"success": True, "download_id": uid, "output_filename": "merged.mp4"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de la fusion")
    finally:
        for p in input_paths:
            p.unlink(missing_ok=True)


# ---- Ajouter texte/sous-titre sur vidéo ----
_VALID_TEXT_POSITIONS = {"bottom", "top", "center", "bottom-left", "bottom-right", "top-left", "top-right"}

@app.post("/video/add-text")
async def video_add_text(
    file: UploadFile = File(...),
    text: str = Form(...),
    position: str = Form("bottom"),
    font_size: int = Form(48),
    font_color: str = Form("white"),
    start_time: float = Form(None),
    end_time: float = Form(None),
):
    if not text or len(text) > 200:
        raise HTTPException(status_code=400, detail="Texte invalide (1-200 caractères).")
    if position not in _VALID_TEXT_POSITIONS:
        raise HTTPException(status_code=400, detail="Position invalide.")
    if font_size < 10 or font_size > 200:
        raise HTTPException(status_code=400, detail="Taille de police invalide (10-200).")
    uid = uuid.uuid4().hex
    ext = Path(file.filename or "video.mp4").suffix.lower() or ".mp4"
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    output_path = OUTPUT_DIR / f"{uid}_output{ext}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["video"])
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: add_text_video(
                input_path, output_path,
                text=text, position=position,
                font_size=font_size, font_color=font_color,
                start_time=start_time, end_time=end_time,
            )
        )
        stem = Path(file.filename).stem
        return {"success": True, "download_id": uid, "output_filename": stem + "_text" + result.suffix}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de l'ajout du texte")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Redimensionner image ----
@app.post("/image/resize")
async def image_resize(
    file: UploadFile = File(...),
    width: int = Form(None),
    height: int = Form(None),
    keep_ratio: bool = Form(True),
):
    uid = uuid.uuid4().hex
    ext = Path(file.filename).suffix.lower()
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["image"])
        output_path = OUTPUT_DIR / f"{uid}_output{ext}"
        result = resize_image(input_path, output_path, width=width, height=height, keep_ratio=keep_ratio)
        output_filename = Path(file.filename).stem + "_resized" + result.suffix
        return {"success": True, "download_id": uid, "output_filename": output_filename}
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Convertir image ----
@app.post("/image/convert")
async def image_convert(
    file: UploadFile = File(...),
    target_format: str = Form("webp"),
):
    uid = uuid.uuid4().hex
    ext = Path(file.filename).suffix.lower()
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["image"])
        output_path = OUTPUT_DIR / f"{uid}_output{ext}"
        result = convert_image(input_path, output_path, target_format=target_format)
        output_filename = Path(file.filename).stem + "_converted" + result.suffix
        return {"success": True, "download_id": uid, "output_filename": output_filename}
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Recadrer image ----
@app.post("/image/crop")
async def image_crop(
    file: UploadFile = File(...),
    left: int = Form(0),
    top: int = Form(0),
    right: int = Form(...),
    bottom: int = Form(...),
):
    uid = uuid.uuid4().hex
    ext = Path(file.filename).suffix.lower()
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["image"])
        output_path = OUTPUT_DIR / f"{uid}_output{ext}"
        result = crop_image(input_path, output_path, left=left, top=top, right=right, bottom=bottom)
        output_filename = Path(file.filename).stem + "_cropped" + result.suffix
        return {"success": True, "download_id": uid, "output_filename": output_filename}
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Rotation / flip image ----
@app.post("/image/rotate")
async def image_rotate(
    file: UploadFile = File(...),
    angle: int = Form(None),
    flip: str = Form(None),
):
    uid = uuid.uuid4().hex
    ext = Path(file.filename).suffix.lower()
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["image"])
        output_path = OUTPUT_DIR / f"{uid}_output{ext}"
        result = rotate_image(input_path, output_path, angle=angle or 0, flip=flip)
        output_filename = Path(file.filename).stem + "_rotated" + result.suffix
        return {"success": True, "download_id": uid, "output_filename": output_filename}
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du fichier")
    finally:
        input_path.unlink(missing_ok=True)


@app.delete("/cleanup/{uid}")
async def cleanup(uid: str):
    _validate_uid(uid)
    for f in OUTPUT_DIR.glob(f"{uid}_*"):
        f.unlink(missing_ok=True)
    return {"cleaned": True}


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.1.0"}


@app.get("/status")
async def status():
    if not _IS_LOCAL:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "version": "1.1.0",
        "ffmpeg": _FFMPEG_AVAILABLE,
        "libreoffice": OFFICE_AVAILABLE,
        "uptime_seconds": round(time.time() - _APP_START, 1),
        "uploads_dir_mb": _dir_size_mb(UPLOAD_DIR),
        "outputs_dir_mb": _dir_size_mb(OUTPUT_DIR),
    }


@app.get("/status-page", response_class=HTMLResponse)
async def status_page_route():
    path = BASE_DIR / "static" / "status.html"
    return HTMLResponse(content=path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    port = 8000
    url = f"http://localhost:{port}"

    print("\n" + "="*50)
    print("  CompressIt — Serveur local")
    print(f"  Ouverture automatique sur : {url}")
    print("="*50 + "\n")

    # Ouvrir le navigateur après 1.2s (temps que le serveur démarre)
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=False)
