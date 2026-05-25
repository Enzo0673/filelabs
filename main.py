"""
CompressIt - Serveur FastAPI local
Lance avec : py main.py  (ou  uvicorn main:app --reload)
Accès : http://localhost:8000
"""

import os
import sys
import uuid
import shutil
import mimetypes
import threading
import webbrowser
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from compressors.image import compress_image
from compressors.pdf import compress_pdf
from compressors.video import compress_video
from compressors.archive import compress_archive
from compressors.pdf_tools import (
    merge_pdfs, split_pdf, pdf_to_jpg, jpg_to_pdf,
    rotate_pdf, watermark_pdf, add_page_numbers,
    delete_pages, unlock_pdf, protect_pdf,
)

# Résolution des chemins compatible PyInstaller (--onefile extrait dans sys._MEIPASS)
if getattr(sys, "frozen", False):
    # Exécutable PyInstaller : fichiers embarqués dans le bundle
    _BUNDLE_DIR = Path(sys._MEIPASS)
    # Uploads/outputs à côté de l'exe, pas dans le temp
    _EXE_DIR = Path(sys.executable).parent
else:
    _BUNDLE_DIR = Path(__file__).parent
    _EXE_DIR = Path(__file__).parent

BASE_DIR = _BUNDLE_DIR
UPLOAD_DIR = _EXE_DIR / "uploads"
OUTPUT_DIR = _EXE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="CompressIt", version="1.0.0")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/service-worker.js")
async def service_worker():
    sw_path = BASE_DIR / "static" / "service-worker.js"
    return FileResponse(path=sw_path, media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})


@app.get("/static/service-worker.js")
async def service_worker_static():
    sw_path = BASE_DIR / "static" / "service-worker.js"
    return FileResponse(path=sw_path, media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})


@app.get("/tool/{tool_name}", response_class=HTMLResponse)
async def tool_page(tool_name: str):
    tool_path = BASE_DIR / "static" / "tools" / f"{tool_name}.html"
    if not tool_path.exists():
        raise HTTPException(status_code=404, detail="Outil introuvable")
    return HTMLResponse(content=tool_path.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = BASE_DIR / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

@app.post("/compress")
async def compress(
    file: UploadFile = File(...),
    level: str = Form("standard"),        # light | standard | aggressive
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
    # Sauvegarder le fichier uploadé
    uid = uuid.uuid4().hex
    original_ext = Path(file.filename).suffix.lower()
    input_path = UPLOAD_DIR / f"{uid}_input{original_ext}"

    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    original_size = input_path.stat().st_size
    mime = file.content_type or mimetypes.guess_type(file.filename)[0] or ""
    file_type = detect_type(file.filename, mime)

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
            output_path = compress_video(
                input_path, output_path, level,
                crf=vid_crf, codec=vid_codec, preset=vid_preset, max_height=vid_max_height
            )
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
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        input_path.unlink(missing_ok=True)


@app.get("/download/{uid}")
async def download(uid: str):
    # Chercher le fichier output correspondant
    matches = list(OUTPUT_DIR.glob(f"{uid}_output*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Fichier introuvable ou expiré")
    output_path = matches[0]
    return FileResponse(
        path=output_path,
        filename=output_path.name,
        background=None,
    )


# ---- Fusionner PDF ----
@app.post("/pdf/merge")
async def pdf_merge(files: List[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Au moins 2 fichiers requis")
    uid = uuid.uuid4().hex
    input_paths = []
    try:
        for i, f in enumerate(files):
            p = UPLOAD_DIR / f"{uid}_input_{i}.pdf"
            with open(p, "wb") as fh:
                shutil.copyfileobj(f.file, fh)
            input_paths.append(p)
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        result = merge_pdfs(input_paths, output_path)
        return {"success": True, "download_id": uid, "output_filename": "merged.pdf"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for p in input_paths:
            p.unlink(missing_ok=True)


# ---- Diviser PDF ----
@app.post("/pdf/split")
async def pdf_split(
    file: UploadFile = File(...),
    ranges: str = Form(None),
):
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        with open(input_path, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        output_dir = OUTPUT_DIR / uid
        result = split_pdf(input_path, output_dir, ranges)
        output_path = OUTPUT_DIR / f"{uid}_output.zip"
        result.rename(output_path)
        return {"success": True, "download_id": uid, "output_filename": "split_result.zip"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        input_path.unlink(missing_ok=True)


# ---- PDF vers JPG ----
@app.post("/pdf/to-jpg")
async def pdf_to_jpg_route(
    file: UploadFile = File(...),
    dpi: int = Form(150),
):
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        with open(input_path, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        output_path = OUTPUT_DIR / f"{uid}_output.zip"
        pdf_to_jpg(input_path, output_path, dpi=dpi)
        return {"success": True, "download_id": uid, "output_filename": "pages.zip"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
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
            with open(p, "wb") as fh:
                shutil.copyfileobj(f.file, fh)
            input_paths.append(p)
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        jpg_to_pdf(input_paths, output_path)
        return {"success": True, "download_id": uid, "output_filename": "images.pdf"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for p in input_paths:
            p.unlink(missing_ok=True)


# ---- Rotation PDF ----
@app.post("/pdf/rotate")
async def pdf_rotate(
    file: UploadFile = File(...),
    angle: int = Form(90),
    pages: str = Form("all"),
):
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        with open(input_path, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        rotate_pdf(input_path, output_path, angle=angle, pages=pages)
        return {"success": True, "download_id": uid, "output_filename": "rotated.pdf"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        input_path.unlink(missing_ok=True)


# ---- Filigrane PDF ----
@app.post("/pdf/watermark")
async def pdf_watermark(
    file: UploadFile = File(...),
    text: str = Form("CONFIDENTIEL"),
    opacity: float = Form(0.3),
):
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        with open(input_path, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        watermark_pdf(input_path, output_path, text=text, opacity=opacity)
        return {"success": True, "download_id": uid, "output_filename": "watermarked.pdf"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        input_path.unlink(missing_ok=True)


# ---- Numéroter pages ----
@app.post("/pdf/page-numbers")
async def pdf_page_numbers(
    file: UploadFile = File(...),
    position: str = Form("bottom-center"),
):
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    try:
        with open(input_path, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        add_page_numbers(input_path, output_path, position=position)
        return {"success": True, "download_id": uid, "output_filename": "numbered.pdf"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
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
        with open(input_path, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        delete_pages(input_path, output_path, pages_to_delete=pages)
        return {"success": True, "download_id": uid, "output_filename": "result.pdf"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
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
        with open(input_path, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        unlock_pdf(input_path, output_path, password=password)
        return {"success": True, "download_id": uid, "output_filename": "unlocked.pdf"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
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
        with open(input_path, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        output_path = OUTPUT_DIR / f"{uid}_output.pdf"
        protect_pdf(input_path, output_path, password=password)
        return {"success": True, "download_id": uid, "output_filename": "protected.pdf"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        input_path.unlink(missing_ok=True)


@app.delete("/cleanup/{uid}")
async def cleanup(uid: str):
    for f in OUTPUT_DIR.glob(f"{uid}_*"):
        f.unlink(missing_ok=True)
    return {"cleaned": True}


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


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
