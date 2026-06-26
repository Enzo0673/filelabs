"""
FileLab — Video Downloader
Wrapper yt-dlp pour téléchargement multi-plateforme (YouTube, TikTok, Instagram, etc.)
"""
import ipaddress
import json
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


class DownloaderError(Exception):
    """Erreur métier du downloader (URL invalide, durée excessive, etc.)"""
    pass


MAX_DURATION_SECONDS = 7200   # 2 heures
MAX_SIZE_BYTES = 2 * 1024 ** 3  # 2 Go

# Plages IP bloquées pour prévenir le SSRF
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("::1/128"),
]


def _validate_url(url: str) -> None:
    """
    Valide l'URL et bloque les IPs privées/internes (SSRF).

    Limitation connue (accepted risk) : TOCTOU DNS rebinding.
    Cette fonction résout le DNS au moment de la validation, mais yt-dlp
    effectue sa propre résolution DNS lors du téléchargement. Un attacker
    contrôlant un domaine avec un TTL très court pourrait changer la résolution
    entre ces deux instants. Atténuants : timing difficile à maîtriser, yt-dlp
    timeout à 30s, et l'attaque nécessite un contrôle DNS externe.
    Mitigation complète : utiliser un proxy DNS filtrant (hors périmètre).

    Raises:
        DownloaderError: URL invalide ou IP interne détectée
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise DownloaderError("Seules les URLs http:// et https:// sont acceptées.")
    hostname = parsed.hostname
    if not hostname:
        raise DownloaderError("URL invalide : hostname manquant.")

    # Résolution DNS + vérification de chaque adresse retournée
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
    _validate_url(url)
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
    _validate_url(url)
    import re as _re
    if not _re.fullmatch(r'[a-zA-Z0-9+\-/_.]+', format_id):
        raise DownloaderError("format_id invalide.")
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
