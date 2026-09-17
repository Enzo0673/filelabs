"""
Filtres et effets image — Pillow pur
- Filigrane texte ou logo
- N&B / Sépia
- Agrandissement (upscale)
"""

from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

_VALID_POSITIONS = {"top-left", "top-right", "bottom-left", "bottom-right", "center"}
_VALID_SCALES = {"2x": 2, "3x": 3, "4x": 4}
_MAX_MP = 50_000_000  # 50 mégapixels


def watermark_image(
    input_path: Path,
    output_path: Path,
    text: Optional[str] = None,
    logo_path: Optional[Path] = None,
    position: str = "bottom-right",
    opacity: int = 50,
) -> Path:
    """Applique un filigrane texte ou logo sur une image."""
    if not text and not logo_path:
        raise ValueError("Fournir text ou logo_path")
    if position not in _VALID_POSITIONS:
        raise ValueError(f"position invalide : {position!r}")
    opacity = max(0, min(100, opacity))
    alpha = int(opacity / 100 * 255)

    base = Image.open(input_path).convert("RGBA")
    w, h = base.size
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))

    if text:
        draw = ImageDraw.Draw(overlay)
        try:
            font = ImageFont.truetype("arial.ttf", size=max(12, w // 20))
        except (OSError, IOError):
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x, y = _compute_pos(position, w, h, tw, th, margin=10)
        draw.text((x, y), text, font=font, fill=(255, 255, 255, alpha))
    else:
        logo = Image.open(logo_path).convert("RGBA")
        logo_w = max(10, w // 5)
        ratio = logo_w / logo.width
        logo_h = int(logo.height * ratio)
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        # Appliquer opacité au canal alpha du logo
        r, g, b, a = logo.split()
        a = a.point(lambda p: int(p * alpha / 255))
        logo = Image.merge("RGBA", (r, g, b, a))
        x, y = _compute_pos(position, w, h, logo_w, logo_h, margin=10)
        overlay.paste(logo, (x, y), logo)

    result = Image.alpha_composite(base, overlay).convert("RGB")
    result.save(output_path)
    return output_path


def _compute_pos(position: str, w: int, h: int, ew: int, eh: int, margin: int) -> tuple:
    if position == "top-left":
        return margin, margin
    if position == "top-right":
        return w - ew - margin, margin
    if position == "bottom-left":
        return margin, h - eh - margin
    if position == "bottom-right":
        return w - ew - margin, h - eh - margin
    # center
    return (w - ew) // 2, (h - eh) // 2


def apply_filter(input_path: Path, output_path: Path, filter_name: str) -> Path:
    """Applique un filtre couleur (grayscale ou sepia)."""
    if filter_name not in ("grayscale", "sepia"):
        raise ValueError(f"Filtre invalide : {filter_name!r} (attendu 'grayscale' ou 'sepia')")

    img = Image.open(input_path).convert("RGB")

    if filter_name == "grayscale":
        img = img.convert("L").convert("RGB")
    else:  # sepia
        pixels = img.load()
        width, height = img.size
        for py in range(height):
            for px in range(width):
                r, g, b = pixels[px, py]
                tr = min(255, int(r * 0.393 + g * 0.769 + b * 0.189))
                tg = min(255, int(r * 0.349 + g * 0.686 + b * 0.168))
                tb = min(255, int(r * 0.272 + g * 0.534 + b * 0.131))
                pixels[px, py] = (tr, tg, tb)

    img.save(output_path)
    return output_path


def upscale_image(input_path: Path, output_path: Path, scale: str = "2x") -> Path:
    """Agrandit une image par un facteur entier (2x, 3x, 4x)."""
    if scale not in _VALID_SCALES:
        raise ValueError(f"scale invalide : {scale!r} (attendu 2x, 3x ou 4x)")

    factor = _VALID_SCALES[scale]
    with Image.open(input_path) as img:
        new_w = img.width * factor
        new_h = img.height * factor

        if new_w * new_h > _MAX_MP:
            raise ValueError(
                f"Résultat trop grand ({new_w}x{new_h} = {new_w*new_h//1_000_000} MP) "
                f"— limite : 50 MP"
            )

        result = img.resize((new_w, new_h), Image.LANCZOS)

    result.save(output_path)
    return output_path
