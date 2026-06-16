"""
Outils image avancés — Pillow
- Redimensionner
- Convertir format
- Recadrer
- Rotation / Flip
"""

from pathlib import Path
from PIL import Image

EXT_MAP = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif", "BMP": ".bmp", "TIFF": ".tiff"}
FMT_MAP = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP", "gif": "GIF", "bmp": "BMP", "tiff": "TIFF", "tif": "TIFF"}


def _open(input_path: Path) -> Image.Image:
    img = Image.open(input_path)
    if img.mode == "P":
        img = img.convert("RGBA")
    return img


def _to_rgb_if_needed(img: Image.Image, fmt: str) -> Image.Image:
    if fmt == "JPEG" and img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode in ("RGBA", "LA"):
            bg.paste(img, mask=img.split()[-1])
        else:
            bg.paste(img)
        return bg
    return img


# ---- Redimensionner ----
def resize_image(
    input_path: Path,
    output_path: Path,
    width: int = None,
    height: int = None,
    keep_ratio: bool = True,
) -> Path:
    img = _open(input_path)
    orig_w, orig_h = img.size

    if width and height and not keep_ratio:
        new_size = (width, height)
    elif width and height and keep_ratio:
        ratio = min(width / orig_w, height / orig_h)
        new_size = (int(orig_w * ratio), int(orig_h * ratio))
    elif width:
        ratio = width / orig_w
        new_size = (width, int(orig_h * ratio))
    elif height:
        ratio = height / orig_h
        new_size = (int(orig_w * ratio), height)
    else:
        raise ValueError("Largeur ou hauteur requise")

    img = img.resize(new_size, Image.LANCZOS)
    ext = input_path.suffix.lower()
    fmt = FMT_MAP.get(ext.lstrip("."), "JPEG")
    img = _to_rgb_if_needed(img, fmt)
    output_path = output_path.with_suffix(EXT_MAP.get(fmt, ext))
    img.save(output_path, format=fmt, quality=90, optimize=True)
    return output_path


# ---- Convertir format ----
def convert_image(
    input_path: Path,
    output_path: Path,
    target_format: str = "webp",
) -> Path:
    fmt = FMT_MAP.get(target_format.lower(), "JPEG")
    img = _open(input_path)
    img = _to_rgb_if_needed(img, fmt)
    output_path = output_path.with_suffix(EXT_MAP.get(fmt, ".jpg"))
    save_kwargs = {}
    if fmt == "JPEG":
        save_kwargs = {"quality": 90, "optimize": True, "progressive": True}
    elif fmt == "WEBP":
        save_kwargs = {"quality": 90, "method": 6}
    elif fmt == "PNG":
        save_kwargs = {"optimize": True}
    img.save(output_path, format=fmt, **save_kwargs)
    return output_path


# ---- Recadrer ----
def crop_image(
    input_path: Path,
    output_path: Path,
    left: int,
    top: int,
    right: int,
    bottom: int,
) -> Path:
    img = _open(input_path)
    w, h = img.size
    left   = max(0, min(left, w))
    top    = max(0, min(top, h))
    right  = max(left + 1, min(right, w))
    bottom = max(top + 1, min(bottom, h))
    img = img.crop((left, top, right, bottom))
    ext = input_path.suffix.lower()
    fmt = FMT_MAP.get(ext.lstrip("."), "JPEG")
    img = _to_rgb_if_needed(img, fmt)
    output_path = output_path.with_suffix(EXT_MAP.get(fmt, ext))
    img.save(output_path, format=fmt, quality=90, optimize=True)
    return output_path


# ---- Rotation / Flip ----
def rotate_image(
    input_path: Path,
    output_path: Path,
    angle: int = 90,
    flip: str = None,   # "horizontal" | "vertical" | None
) -> Path:
    img = _open(input_path)
    if flip == "horizontal":
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    elif flip == "vertical":
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    if angle:
        img = img.rotate(-angle, expand=True)
    ext = input_path.suffix.lower()
    fmt = FMT_MAP.get(ext.lstrip("."), "JPEG")
    img = _to_rgb_if_needed(img, fmt)
    output_path = output_path.with_suffix(EXT_MAP.get(fmt, ext))
    img.save(output_path, format=fmt, quality=90, optimize=True)
    return output_path
