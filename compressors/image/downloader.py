"""
FileLab — Image Downloader
Téléchargement d'images depuis Instagram, Pinterest, Twitter/X, Facebook via yt-dlp.
"""
import ipaddress
import json
import socket
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from compressors.media.downloader import _BLOCKED_NETWORKS, DownloaderError


def _validate_url(url: str) -> None:
    """Valide l'URL et bloque les IPs internes (SSRF)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise DownloaderError("Seules les URLs http:// et https:// sont acceptées.")
    hostname = parsed.hostname
    if not hostname:
        raise DownloaderError("URL invalide : hostname manquant.")
    try:
        addrs = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise DownloaderError("Impossible de résoudre le nom d'hôte.")
    for addr_info in addrs:
        ip_str = addr_info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise DownloaderError("URL non autorisée.")


def get_media_info(url: str) -> dict:
    """
    Analyse une URL et retourne les images disponibles.

    Returns:
        {
            "title": str,
            "images": [
                {"index": int, "thumbnail": str, "ext": str},
                ...
            ]
        }

    Raises:
        DownloaderError
    """
    _validate_url(url)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--dump-json", "--no-playlist", url],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise DownloaderError("L'analyse a pris trop de temps.")
    except FileNotFoundError:
        raise DownloaderError("yt-dlp n'est pas installé.")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "Unsupported URL" in stderr:
            raise DownloaderError("URL non supportée ou plateforme non reconnue.")
        if "unavailable" in stderr.lower() or "private" in stderr.lower():
            raise DownloaderError("Contenu indisponible ou privé.")
        raise DownloaderError(f"Impossible d'analyser l'URL : {stderr[:200]}")

    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise DownloaderError("Réponse inattendue de yt-dlp.")

    title = raw.get("title") or raw.get("description") or "Sans titre"

    # Cas 1 : plusieurs images dans un carousel (entries ou requested_downloads)
    images = []

    # Certains extracteurs exposent les images dans formats avec vcodec=none et ext image
    formats = raw.get("formats", [])
    image_formats = [
        f for f in formats
        if f.get("vcodec") in (None, "none")
        and f.get("acodec") in (None, "none")
        and f.get("ext") in ("jpg", "jpeg", "png", "webp")
    ]

    if image_formats:
        seen = set()
        for fmt in image_formats:
            url_f = fmt.get("url", "")
            if url_f and url_f not in seen:
                seen.add(url_f)
                images.append({
                    "index": len(images),
                    "thumbnail": url_f,
                    "ext": fmt.get("ext", "jpg"),
                    "url": url_f,
                })
    else:
        # Fallback : image unique via thumbnail
        thumb = raw.get("thumbnail") or raw.get("url", "")
        ext = "jpg"
        if thumb.endswith(".png"):
            ext = "png"
        elif thumb.endswith(".webp"):
            ext = "webp"
        if thumb:
            images.append({"index": 0, "thumbnail": thumb, "ext": ext, "url": thumb})

    if not images:
        raise DownloaderError("Aucune image trouvée à cette URL.")

    return {"title": title[:200], "images": images}


def download_images(url: str, indices: list[int], output_dir: Path) -> Path:
    """
    Télécharge les images sélectionnées par index.

    Returns:
        Path : fichier image direct (si 1 image) ou ZIP (si plusieurs)

    Raises:
        DownloaderError
    """
    _validate_url(url)

    if not indices:
        raise DownloaderError("Aucune image sélectionnée.")
    if len(indices) > 50:
        raise DownloaderError("Maximum 50 images à la fois.")

    # Récupérer les infos pour avoir les URLs
    info = get_media_info(url)
    images = info["images"]

    selected = []
    for idx in indices:
        if 0 <= idx < len(images):
            selected.append(images[idx])

    if not selected:
        raise DownloaderError("Index d'images invalides.")

    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded_paths = []

    for img in selected:
        img_url = img["url"]
        _validate_url(img_url)          # CWE-918 : re-valider l'URL issue de yt-dlp
        ext = img["ext"]
        dest = output_dir / f"image_{img['index']}.{ext}"
        try:
            dl = subprocess.run(
                [sys.executable, "-m", "yt_dlp",
                 "--no-playlist",
                 "-o", str(dest),
                 img_url],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if dest.exists():
                downloaded_paths.append(dest)
            else:
                # Chercher le fichier créé (extension peut varier)
                matches = list(output_dir.glob(f"image_{img['index']}.*"))
                if matches:
                    downloaded_paths.append(matches[0])
        except subprocess.TimeoutExpired:
            raise DownloaderError("Téléchargement trop long.")

    if not downloaded_paths:
        raise DownloaderError("Échec du téléchargement des images.")

    if len(downloaded_paths) == 1:
        return downloaded_paths[0]

    # Plusieurs images → ZIP
    zip_path = output_dir / "images.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in downloaded_paths:
            zf.write(p, p.name)
    return zip_path
