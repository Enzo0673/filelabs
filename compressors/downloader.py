"""
CompressIt — Video Downloader
Wrapper yt-dlp pour téléchargement multi-plateforme (YouTube, TikTok, Instagram, etc.)
"""
import json
import subprocess
import sys
from pathlib import Path


class DownloaderError(Exception):
    """Erreur métier du downloader (URL invalide, durée excessive, etc.)"""
    pass


MAX_DURATION_SECONDS = 7200   # 2 heures
MAX_SIZE_BYTES = 2 * 1024 ** 3  # 2 Go


def _run_ytdlp_info(url: str) -> dict:
    """Appelle yt-dlp --dump-json et retourne le dict parsé."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--dump-json", "--no-playlist", url],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise DownloaderError("L'analyse de la vidéo a pris trop de temps.")
    except FileNotFoundError:
        raise DownloaderError("yt-dlp n'est pas installé.")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "Unsupported URL" in stderr:
            raise DownloaderError("URL non supportée ou plateforme non reconnue.")
        if "Video unavailable" in stderr or "Private video" in stderr:
            raise DownloaderError("Vidéo indisponible ou privée.")
        raise DownloaderError(f"Impossible d'analyser l'URL : {stderr[:200]}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise DownloaderError("Réponse inattendue de yt-dlp.")


def get_video_info(url: str) -> dict:
    """
    Analyse une URL et retourne les infos + formats disponibles.

    Returns:
        {
            "title": str,
            "thumbnail": str,
            "duration": int,  # secondes
            "formats": [
                {"format_id": str, "label": str, "ext": str},
                ...
            ]
        }

    Raises:
        DownloaderError: URL invalide, plateforme non supportée, durée > 2h
    """
    raw = _run_ytdlp_info(url)

    duration = raw.get("duration") or 0
    if duration > MAX_DURATION_SECONDS:
        raise DownloaderError(
            f"Vidéo trop longue ({int(duration // 60)} min). Limite : 2 heures."
        )

    # Construire la liste des formats MP4 disponibles
    formats = [{"format_id": "bestvideo+bestaudio/best", "label": "Meilleure qualité", "ext": "mp4"}]

    seen_heights = set()
    for fmt in raw.get("formats", []):
        height = fmt.get("height")
        ext = fmt.get("ext", "")
        vcodec = fmt.get("vcodec", "none")
        # Garder uniquement les formats vidéo MP4/WebM avec une résolution connue
        if not height or vcodec == "none" or ext not in ("mp4", "webm"):
            continue
        if height in seen_heights:
            continue
        seen_heights.add(height)
        label = f"{height}p"
        if height >= 2160:
            label = f"4K ({height}p)"
        formats.append({
            "format_id": fmt["format_id"],
            "label": label,
            "ext": "mp4",
        })

    # Trier par résolution décroissante (après le premier "Meilleure qualité")
    formats[1:] = sorted(formats[1:], key=lambda f: int(f["label"].split("p")[0].split("(")[-1]) if "p" in f["label"] else 0, reverse=True)

    return {
        "title": raw.get("title", "Vidéo sans titre"),
        "thumbnail": raw.get("thumbnail", ""),
        "duration": int(duration),
        "formats": formats,
    }


def download_media(url: str, mode: str, format_id: str, output_path: Path, on_progress=None) -> Path:
    """
    Télécharge une vidéo ou extrait l'audio.

    Args:
        url: URL de la vidéo
        mode: "video" ou "audio"
        format_id: format_id yt-dlp pour MP4, ignoré pour "audio"
        output_path: chemin de sortie souhaité (sans extension finale)
        on_progress: callback(float) appelé avec pourcentage 0-100

    Returns:
        Path: chemin réel du fichier créé

    Raises:
        DownloaderError: échec du téléchargement
    """
    if mode == "audio":
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--no-playlist",
            "--newline",
            "-o", str(output_path) + ".%(ext)s",
            url,
        ]
        expected_ext = ".mp3"
    else:
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", format_id,
            "--merge-output-format", "mp4",
            "--no-playlist",
            "--newline",
            "-o", str(output_path) + ".%(ext)s",
            url,
        ]
        expected_ext = ".mp4"

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        raise DownloaderError("yt-dlp n'est pas installé.")

    for line in process.stdout:
        line = line.strip()
        if "[download]" in line and "%" in line:
            try:
                pct_str = line.split("%")[0].split()[-1]
                pct = float(pct_str)
                if on_progress:
                    on_progress(min(pct, 99.0))
            except (ValueError, IndexError):
                pass

    process.wait()
    if process.returncode != 0:
        raise DownloaderError("Le téléchargement a échoué. Vérifiez l'URL.")

    if on_progress:
        on_progress(100.0)

    real_path = Path(str(output_path) + expected_ext)
    if not real_path.exists():
        parent = output_path.parent
        stem = output_path.name
        matches = list(parent.glob(f"{stem}.*"))
        if not matches:
            raise DownloaderError("Fichier téléchargé introuvable.")
        real_path = matches[0]

    return real_path
