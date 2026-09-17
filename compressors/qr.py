"""
QR Code — génération et lecture
Dépendances : qrcode[pil], pyzbar
"""

from pathlib import Path


def generate_qr(text: str, output_path: Path) -> Path:
    """Génère un QR Code PNG à partir d'un texte."""
    if not text or not text.strip():
        raise ValueError("Le texte ne peut pas être vide")

    import qrcode
    output_path = output_path.with_suffix(".png")
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(str(output_path))
    return output_path


def read_qr(input_path: Path) -> dict:
    """Lit un QR Code depuis une image. Retourne {"data": str | None}."""
    from PIL import Image
    try:
        from pyzbar.pyzbar import decode
    except ImportError:
        raise ImportError("pyzbar requis pour lire les QR codes (pip install pyzbar)")

    img = Image.open(input_path)
    decoded = decode(img)
    if not decoded:
        return {"data": None}
    return {"data": decoded[0].data.decode("utf-8")}
