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


def compress_video(
    input_path: Path,
    output_path: Path,
    level: str = "standard",
    crf: int = None,
    codec: str = "h264",
    preset: str = "medium",
    max_height: int = None,
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
        # Redimensionner seulement si la vidéo est plus grande que la cible
        video = ffmpeg.filter(
            video, "scale",
            w=-2, h=f"min({target_height},ih)",
        )

    audio = input_stream.audio

    # Paramètres codec
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

    out = ffmpeg.output(
        video, audio,
        str(output_path),
        **video_kwargs,
        **audio_kwargs,
        movflags="+faststart" if codec_key != "vp9" else None,
        loglevel="error",
    )

    # Supprimer None kwargs
    out = out.global_args("-hide_banner", "-threads", "0")

    ffmpeg.run(out, overwrite_output=True, quiet=True)
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
