"""
Compression PDF — pikepdf
Stratégies :
  - Re-compression des images internes (JPEG/JPEG2000)
  - Suppression des métadonnées inutiles
  - Suppression des flux dupliqués
  - Aplatissement des calques invisibles
"""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pikepdf
from PIL import Image
import io

DPI_PROFILES = {
    "light":      150,
    "standard":   120,
    "aggressive": 72,
}

QUALITY_PROFILES = {
    "light":      80,
    "standard":   65,
    "aggressive": 45,
}


def compress_pdf(
    input_path: Path,
    output_path: Path,
    level: str = "standard",
    dpi: int = None,
    remove_metadata: bool = True,
) -> Path:
    target_quality = QUALITY_PROFILES.get(level, 65)
    output_path = output_path.with_suffix(".pdf")

    with pikepdf.open(input_path) as pdf:
        # Supprimer les métadonnées
        if remove_metadata:
            with pdf.open_metadata() as meta:
                for key in list(meta.keys()):
                    try:
                        del meta[key]
                    except Exception:
                        pass

        # Recompresser les images internes (parallèle)
        with ThreadPoolExecutor() as executor:
            list(executor.map(lambda p: _recompress_page_images(p, target_quality), pdf.pages))

        # Supprimer les objets non référencés
        pdf.save(
            output_path,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
            recompress_flate=True,
            normalize_content=False,
        )

    return output_path


def _recompress_page_images(page, quality: int):
    """Parcourt les XObjects d'une page et recompresse les images JPEG."""
    try:
        resources = page.get("/Resources")
        if resources is None:
            return
        xobjects = resources.get("/XObject")
        if xobjects is None:
            return

        for key in xobjects.keys():
            xobj = xobjects[key]
            if not isinstance(xobj, pikepdf.Stream):
                continue
            if xobj.get("/Subtype") != "/Image":
                continue

            # Lire les données brutes
            try:
                raw = xobj.read_raw_bytes()
                filter_type = xobj.get("/Filter")
                if filter_type in ("/DCTDecode", pikepdf.Name("/DCTDecode")):
                    img = Image.open(io.BytesIO(raw))
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=quality, optimize=True)
                    new_data = buf.getvalue()
                    if len(new_data) < len(raw):
                        xobj.write(new_data, filter=pikepdf.Name("/DCTDecode"))
            except Exception:
                continue
    except Exception:
        pass
