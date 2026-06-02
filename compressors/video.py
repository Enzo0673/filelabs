"""
Compression vidéo — ffmpeg-python
Codecs supportés : H.264 (h264), H.265/HEVC (h265), VP9 (vp9)
FFmpeg peut être placé dans compressit/bin/ffmpeg.exe (pas besoin d'installation système)
"""

from pathlib import Path
import ffmpeg
import subprocess
import shutil
import os
import re as _re
from typing import Callable, Optional

# CRF par niveau (plus le chiffre est haut, plus la compression est forte)
# H.264 : 18 (visuel lossless) → 28 (bon) → 35 (agressif)
CRF_PROFILES = {
    "h264": {"light": 22, "standard": 28, "aggressive": 35},
    "h265": {"light": 24, "standard": 30, "aggressive": 38},
    "vp9":  {"light": 30, "standard": 38, "aggressive": 48},
}

CODEC_MAP = {
    "h264": "libx264",
    "h265": "libx265",
    "vp9":  "libvpx-vp9",
}

EXT_MAP = {
    "h264": ".mp4",
    "h265": ".mp4",
    "vp9":  ".webm",
}

HEIGHT_PROFILES = {
    "light":      None,   # Pas de redimensionnement
    "standard":   1080,
    "aggressive": 720,
}

# Dossier bin/ local au projet (prioritaire sur le PATH système)
_BIN_DIR = Path(__file__).parent.parent / "bin"


def _find_ffmpeg() -> str:
    """Cherche ffmpeg.exe dans bin/ local, puis dans le PATH système."""
    local = _BIN_DIR / "ffmpeg.exe"
    if local.is_file():
        return str(local)
    found = shutil.which("ffmpeg")
    if found:
        return found
    return None


FFMPEG_AVAILABLE = _find_ffmpeg() is not None


def compress_video(
    input_path: Path,
    output_path: Path,
    level: str = "standard",
    crf: int = None,
    codec: str = "h264",
    preset: str = "medium",
    max_height: int = None,
    on_progress: Optional[Callable[[float], None]] = None,
) -> Path:
    ffmpeg_exe = _find_ffmpeg()
    if not ffmpeg_exe:
        raise RuntimeError(
            "FFmpeg introuvable. Placez ffmpeg.exe dans le dossier compressit/bin/ "
            "(téléchargement : https://www.gyan.dev/ffmpeg/builds/ → ffmpeg-release-essentials.zip, "
            "extrayez uniquement bin/ffmpeg.exe dans compressit/bin/)."
        )

    # Indiquer à ffmpeg-python quel exécutable utiliser
    os.environ["PATH"] = str(_BIN_DIR) + os.pathsep + os.environ.get("PATH", "")

    codec_key = codec.lower() if codec else "h264"
    if codec_key not in CODEC_MAP:
        codec_key = "h264"

    out_ext = EXT_MAP[codec_key]
    output_path = output_path.with_suffix(out_ext)

    target_crf = crf if crf is not None else CRF_PROFILES[codec_key].get(level, 28)
    target_height = max_height or HEIGHT_PROFILES.get(level)
    lib = CODEC_MAP[codec_key]

    input_stream = ffmpeg.input(str(input_path))

    # Filtres vidéo
    video = input_stream.video
    if target_height:
        video = ffmpeg.filter(
            video, "scale",
            w=-2, h=f"min({target_height},ih)",
        )

    audio = input_stream.audio

    video_kwargs = {
        "vcodec": lib,
        "crf": target_crf,
    }
    if codec_key in ("h264", "h265"):
        video_kwargs["preset"] = preset
    if codec_key == "h265":
        video_kwargs["x265-params"] = "log-level=error"
    if codec_key == "vp9":
        video_kwargs["b:v"] = 0
        video_kwargs["deadline"] = "good"
        video_kwargs["cpu-used"] = 2

    audio_kwargs = {
        "acodec": "aac" if codec_key != "vp9" else "libopus",
        "b:a": "128k" if level != "aggressive" else "96k",
    }

    output_kwargs = {**video_kwargs, **audio_kwargs, "loglevel": "error"}
    if codec_key != "vp9":
        output_kwargs["movflags"] = "+faststart"
    out = ffmpeg.output(
        video, audio,
        str(output_path),
        **output_kwargs,
    )
    out = out.global_args("-hide_banner", "-threads", "0")

    if on_progress is None:
        ffmpeg.run(out, overwrite_output=True, quiet=True)
        return output_path

    # Récupérer la durée totale pour calculer le pourcentage
    try:
        probe = ffmpeg.probe(str(input_path))
        duration = float(probe["format"]["duration"])
    except Exception:
        duration = None

    # Lancer ffmpeg avec progression sur stderr
    cmd = ffmpeg.compile(out, overwrite_output=True)
    # Remplacer -loglevel error par stats pour avoir les lignes de progression
    try:
        idx = cmd.index("-loglevel")
        cmd[idx + 1] = "error"
    except ValueError:
        pass
    cmd += ["-progress", "pipe:2", "-nostats"]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _time_re = _re.compile(r"out_time_ms=(\d+)")
    for line in proc.stderr:
        m = _time_re.search(line)
        if m and duration:
            elapsed_s = int(m.group(1)) / 1_000_000
            pct = min(99.0, elapsed_s / duration * 100)
            on_progress(pct)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("FFmpeg a retourné une erreur lors de la compression vidéo")
    on_progress(100.0)
    return output_path


def trim_video(input_path: Path, output_path: Path, start: float, end: float) -> Path:
    """Découpe une vidéo entre start et end (en secondes)."""
    ffmpeg_exe = _find_ffmpeg()
    if not ffmpeg_exe:
        raise RuntimeError("FFmpeg introuvable.")
    if end <= start:
        raise ValueError("La fin doit être après le début.")
    os.environ["PATH"] = str(_BIN_DIR) + os.pathsep + os.environ.get("PATH", "")
    ext = input_path.suffix.lower() or ".mp4"
    output_path = output_path.with_suffix(ext)
    out = (
        ffmpeg
        .input(str(input_path), ss=start, to=end)
        .output(str(output_path), c="copy", loglevel="error")
        .global_args("-hide_banner")
    )
    ffmpeg.run(out, overwrite_output=True, quiet=True)
    return output_path


def resize_video(input_path: Path, output_path: Path, width: int = None, height: int = None) -> Path:
    """Redimensionne une vidéo. Conserve le ratio si une seule dimension est donnée."""
    ffmpeg_exe = _find_ffmpeg()
    if not ffmpeg_exe:
        raise RuntimeError("FFmpeg introuvable.")
    if not width and not height:
        raise ValueError("Au moins une dimension requise.")
    os.environ["PATH"] = str(_BIN_DIR) + os.pathsep + os.environ.get("PATH", "")
    ext = input_path.suffix.lower() or ".mp4"
    output_path = output_path.with_suffix(ext)
    # Assure dimensions paires (requis H.264)
    w = str(width) if width else "-2"
    h = str(height) if height else "-2"
    out = (
        ffmpeg
        .input(str(input_path))
        .filter("scale", w=w, h=h)
        .output(str(output_path), vcodec="libx264", crf=18, preset="fast",
                acodec="aac", loglevel="error")
        .global_args("-hide_banner")
    )
    ffmpeg.run(out, overwrite_output=True, quiet=True)
    return output_path


def merge_videos(input_paths: list, output_path: Path) -> Path:
    """Concatène plusieurs vidéos dans l'ordre. Utilise le concat demuxer pour éviter
    les problèmes de splitting de streams avec ffmpeg-python."""
    ffmpeg_exe = _find_ffmpeg()
    if not ffmpeg_exe:
        raise RuntimeError("FFmpeg introuvable.")
    if len(input_paths) < 2:
        raise ValueError("Au moins 2 vidéos requises.")
    os.environ["PATH"] = str(_BIN_DIR) + os.pathsep + os.environ.get("PATH", "")

    output_path = output_path.with_suffix(".mp4")

    # Créer un fichier list temporaire pour le concat demuxer
    list_path = output_path.with_suffix(".txt")
    try:
        with open(list_path, "w", encoding="utf-8") as f:
            for p in input_paths:
                # Échapper les apostrophes dans les chemins
                safe = str(Path(p).resolve()).replace("'", "'\\''")
                f.write(f"file '{safe}'\n")

        cmd = [
            ffmpeg_exe,
            "-hide_banner",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-vcodec", "libx264",
            "-crf", "22",
            "-preset", "fast",
            "-acodec", "aac",
            "-b:a", "128k",
            "-loglevel", "error",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg merge échoué : {result.stderr[:500]}")
    finally:
        if list_path.exists():
            list_path.unlink()

    return output_path


def add_text_video(
    input_path: Path,
    output_path: Path,
    text: str,
    position: str = "bottom",
    font_size: int = 48,
    font_color: str = "white",
    start_time: float = None,
    end_time: float = None,
) -> Path:
    """Ajoute un texte (sous-titre ou watermark) sur la vidéo via le filtre drawtext."""
    ffmpeg_exe = _find_ffmpeg()
    if not ffmpeg_exe:
        raise RuntimeError("FFmpeg introuvable.")
    os.environ["PATH"] = str(_BIN_DIR) + os.pathsep + os.environ.get("PATH", "")

    ext = input_path.suffix.lower() or ".mp4"
    output_path = output_path.with_suffix(ext)

    # Position du texte
    pos_map = {
        "bottom": "(w-text_w)/2:h-th-40",
        "top": "(w-text_w)/2:40",
        "center": "(w-text_w)/2:(h-th)/2",
        "bottom-left": "20:h-th-40",
        "bottom-right": "w-tw-20:h-th-40",
        "top-left": "20:40",
        "top-right": "w-tw-20:40",
    }
    xy = pos_map.get(position, pos_map["bottom"])
    x, y = xy.split(":", 1)

    # Valider font_color : couleur nommée ou hex #RRGGBB(AA) uniquement
    import re as _re_color
    _VALID_COLOR_RE = _re_color.compile(r'^#[0-9a-fA-F]{6,8}$')
    _NAMED_COLORS = {
        "white", "black", "red", "green", "blue", "yellow", "orange",
        "purple", "pink", "gray", "grey", "cyan", "magenta",
    }
    if font_color not in _NAMED_COLORS and not _VALID_COLOR_RE.match(font_color):
        raise ValueError(f"Couleur invalide : {font_color!r}")

    # Sanitiser le texte pour drawtext (échapper les caractères spéciaux)
    safe_text = text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")

    drawtext_opts = {
        "text": safe_text,
        "fontsize": font_size,
        "fontcolor": font_color,
        "x": x,
        "y": y,
        "box": 1,
        "boxcolor": "black@0.4",
        "boxborderw": 8,
    }

    if start_time is not None and end_time is not None:
        drawtext_opts["enable"] = f"'between(t,{start_time},{end_time})'"

    inp = ffmpeg.input(str(input_path))
    video = inp.video.filter("drawtext", **drawtext_opts)
    audio = inp.audio

    out = ffmpeg.output(
        video, audio,
        str(output_path),
        vcodec="libx264",
        crf=18,
        preset="fast",
        acodec="aac",
        loglevel="error",
    ).global_args("-hide_banner")

    ffmpeg.run(out, overwrite_output=True, quiet=True)
    return output_path
