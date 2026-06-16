"""
Compression d'images — Pillow
Formats supportés : JPEG, PNG, WebP, GIF, BMP, TIFF
"""

from pathlib import Path
from PIL import Image

# Profils de qualité par niveau
QUALITY_PROFILES = {
    "light":      {"jpeg": 85, "webp": 85, "png_optimize": False},
    "standard":   {"jpeg": 72, "webp": 72, "png_optimize": True},
    "aggressive": {"jpeg": 50, "webp": 50, "png_optimize": True},
}

# Extensions → format Pillow
EXT_FORMAT = {
    ".jpg":  "JPEG",
    ".jpeg": "JPEG",
    ".png":  "PNG",
    ".webp": "WEBP",
    ".gif":  "GIF",
    ".bmp":  "BMP",
    ".tiff": "TIFF",
    ".tif":  "TIFF",
}


def compress_image(
    input_path: Path,
    output_path: Path,
    level: str = "standard",
    quality: int = None,
    output_format: str = None,
    max_width: int = None,
) -> Path:
    profile = QUALITY_PROFILES.get(level, QUALITY_PROFILES["standard"])
    target_fmt = _resolve_format(input_path, output_format)

    # Context manager : garantit la fermeture du handle (évite WinError 32 à l'unlink)
    with Image.open(input_path) as src:
        # Conversion RGBA → RGB si besoin pour JPEG
        if target_fmt == "JPEG" and src.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", src.size, (255, 255, 255))
            if src.mode == "P":
                src_converted = src.convert("RGBA")
            else:
                src_converted = src
            background.paste(
                src_converted,
                mask=src_converted.split()[3] if src_converted.mode == "RGBA" else None
            )
            img = background
        elif src.mode == "P":
            img = src.convert("RGBA")
        else:
            img = src.copy()  # détache de l'objet source pour permettre la fermeture

        # Redimensionnement si max_width défini (garde le ratio)
        if max_width and img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)

    # Déterminer la qualité
    q = quality if quality is not None else profile["jpeg"]

    # Extension de sortie
    ext_map = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif", "BMP": ".bmp", "TIFF": ".tiff"}
    out_ext = ext_map.get(target_fmt, output_path.suffix)
    output_path = output_path.with_suffix(out_ext)

    save_kwargs = {}
    if target_fmt == "JPEG":
        save_kwargs = {"quality": q, "optimize": True, "progressive": True}
    elif target_fmt == "PNG":
        # PNG compress_level 0-9 (inverse de la qualité)
        compress = 9 if profile["png_optimize"] else 6
        save_kwargs = {"optimize": True, "compress_level": compress}
    elif target_fmt == "WEBP":
        save_kwargs = {"quality": q, "method": 6}
    elif target_fmt == "GIF":
        save_kwargs = {"optimize": True}

    img.save(output_path, format=target_fmt, **save_kwargs)
    return output_path


def _resolve_format(input_path: Path, output_format: str = None) -> str:
    if output_format:
        fmt_map = {"jpeg": "JPEG", "jpg": "JPEG", "png": "PNG", "webp": "WEBP"}
        return fmt_map.get(output_format.lower(), "JPEG")
    return EXT_FORMAT.get(input_path.suffix.lower(), "JPEG")
