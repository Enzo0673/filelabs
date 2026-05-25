"""
Outils PDF avancés — pikepdf
- Fusionner plusieurs PDF
- Diviser un PDF (extraire des pages)
- PDF vers JPG (chaque page en image)
- JPG vers PDF (assembler des images)
- Rotation de pages
- Filigrane texte
- Numérotation des pages
- Suppression de pages
- Déverrouiller PDF (supprimer mot de passe)
- Protéger PDF (ajouter mot de passe)
"""

from pathlib import Path
from typing import List
import pikepdf
from PIL import Image, ImageDraw, ImageFont
import io
import zipfile


# ---- Fusionner PDF ----
def merge_pdfs(input_paths: List[Path], output_path: Path) -> Path:
    output_path = output_path.with_suffix(".pdf")
    pdf_out = pikepdf.Pdf.new()
    for p in input_paths:
        with pikepdf.open(p) as pdf:
            pdf_out.pages.extend(pdf.pages)
    pdf_out.save(output_path, compress_streams=True)
    return output_path


# ---- Diviser PDF ----
def split_pdf(input_path: Path, output_dir: Path, ranges: str = None) -> List[Path]:
    """
    ranges: ex "1-3,5,7-9" (1-indexé). Si None, une page par fichier.
    Retourne une liste de chemins vers les PDF générés, zippés dans un seul fichier.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_files = []

    with pikepdf.open(input_path) as pdf:
        total = len(pdf.pages)

        if ranges:
            page_groups = _parse_ranges(ranges, total)
        else:
            page_groups = [[i] for i in range(total)]

        for idx, group in enumerate(page_groups):
            out = pikepdf.Pdf.new()
            for pg in group:
                if 0 <= pg < total:
                    out.pages.append(pdf.pages[pg])
            if len(out.pages) == 0:
                continue
            part_path = output_dir / f"part_{idx+1}.pdf"
            out.save(part_path, compress_streams=True)
            output_files.append(part_path)

    # Zipper les fichiers générés
    zip_path = output_dir / "split_result.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in output_files:
            zf.write(f, f.name)
            f.unlink()

    return zip_path


def _parse_ranges(ranges_str: str, total: int) -> List[List[int]]:
    groups = []
    for part in ranges_str.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            groups.append(list(range(int(a)-1, int(b))))
        else:
            groups.append([int(part)-1])
    return groups


# ---- PDF vers JPG ----
def pdf_to_jpg(input_path: Path, output_path: Path, dpi: int = 150) -> Path:
    """Convertit chaque page en JPG, retourne un ZIP."""
    from pdf2image import convert_from_path
    zip_path = output_path.with_suffix(".zip")
    images = convert_from_path(str(input_path), dpi=dpi)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for i, img in enumerate(images):
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            zf.writestr(f"page_{i+1:03d}.jpg", buf.getvalue())
    return zip_path


# ---- JPG vers PDF ----
def jpg_to_pdf(input_paths: List[Path], output_path: Path) -> Path:
    output_path = output_path.with_suffix(".pdf")
    images = []
    for p in input_paths:
        img = Image.open(p)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        images.append(img)

    if not images:
        raise ValueError("Aucune image valide fournie")

    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        format="PDF",
    )
    return output_path


# ---- Rotation PDF par map individuelle ----
def rotate_pdf_map(input_path: Path, output_path: Path, rotation_map: str) -> Path:
    """rotation_map = '1:90,3:180,5:270' (pages 1-indexées)"""
    output_path = output_path.with_suffix(".pdf")
    mapping = {}
    for entry in rotation_map.split(','):
        entry = entry.strip()
        if ':' in entry:
            pg, angle = entry.split(':', 1)
            mapping[int(pg) - 1] = int(angle)

    with pikepdf.open(input_path) as pdf:
        for idx, angle in mapping.items():
            if 0 <= idx < len(pdf.pages):
                page = pdf.pages[idx]
                current = int(page.get("/Rotate", 0))
                page["/Rotate"] = (current + angle) % 360
        pdf.save(output_path, compress_streams=True)
    return output_path


# ---- Rotation PDF ----
def rotate_pdf(input_path: Path, output_path: Path, angle: int = 90, pages: str = "all") -> Path:
    output_path = output_path.with_suffix(".pdf")
    with pikepdf.open(input_path) as pdf:
        total = len(pdf.pages)
        if pages == "all":
            target_pages = list(range(total))
        else:
            target_pages = [p-1 for p in _parse_ranges(pages, total)[0]]

        for i in target_pages:
            if 0 <= i < total:
                page = pdf.pages[i]
                current = int(page.get("/Rotate", 0))
                page["/Rotate"] = (current + angle) % 360

        pdf.save(output_path, compress_streams=True)
    return output_path


# ---- Filigrane PDF ----
def watermark_pdf(input_path: Path, output_path: Path, text: str = "CONFIDENTIEL", opacity: float = 0.3) -> Path:
    output_path = output_path.with_suffix(".pdf")
    # Couleur grise avec opacité simulée (PDF ne supporte pas l'alpha sur le texte directement)
    gray = max(0.0, min(1.0, 1.0 - opacity))

    with pikepdf.open(input_path) as pdf:
        for page in pdf.pages:
            mediabox = page.mediabox
            w = float(mediabox[2])
            h = float(mediabox[3])
            cx = w / 2
            cy = h / 2

            # Contenu PDF brut : texte diagonal centré
            watermark_stream = (
                f"q\n"
                f"{gray:.2f} {gray:.2f} {gray:.2f} rg\n"
                f"BT\n"
                f"/Helvetica 48 Tf\n"
                f"{gray:.2f} {gray:.2f} {gray:.2f} rg\n"
                f"1 0 0 1 {cx:.1f} {cy:.1f} Tm\n"
                f"-0.5 0.866 -0.866 -0.5 {cx:.1f} {cy:.1f} Tm\n"
                f"({text}) Tj\n"
                f"ET\n"
                f"Q\n"
            ).encode()

            # Ajouter la police Helvetica aux ressources de la page si absente
            if "/Resources" not in page:
                page["/Resources"] = pikepdf.Dictionary()
            resources = page["/Resources"]
            if "/Font" not in resources:
                resources["/Font"] = pikepdf.Dictionary()
            if "/Helvetica" not in resources["/Font"]:
                resources["/Font"]["/Helvetica"] = pikepdf.Dictionary(
                    Type=pikepdf.Name("/Font"),
                    Subtype=pikepdf.Name("/Type1"),
                    BaseFont=pikepdf.Name("/Helvetica"),
                )

            # Créer le stream filigrane et l'ajouter comme overlay
            wm_stream = pikepdf.Stream(pdf, watermark_stream)
            # Encapsuler le contenu existant et ajouter le filigrane
            existing = page.get("/Contents")
            if existing is None:
                page["/Contents"] = wm_stream
            else:
                if isinstance(existing, pikepdf.Array):
                    existing.append(wm_stream)
                    page["/Contents"] = existing
                else:
                    page["/Contents"] = pikepdf.Array([existing, wm_stream])

        pdf.save(output_path, compress_streams=True)
    return output_path


# ---- Numéroter pages ----
def add_page_numbers(input_path: Path, output_path: Path, position: str = "bottom-center") -> Path:
    output_path = output_path.with_suffix(".pdf")

    with pikepdf.open(input_path) as pdf:
        total = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            # Créer une image avec le numéro de page
            mediabox = page.mediabox
            w = float(mediabox[2])
            h = float(mediabox[3])

            num_img = Image.new("RGBA", (int(w), int(h)), (255, 255, 255, 0))
            draw = ImageDraw.Draw(num_img)
            try:
                font = ImageFont.truetype("arial.ttf", 16)
            except Exception:
                font = ImageFont.load_default()

            text = f"{i+1} / {total}"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]

            if position == "bottom-center":
                x, y = (int(w) - tw) // 2, int(h) - 30
            elif position == "bottom-right":
                x, y = int(w) - tw - 20, int(h) - 30
            else:
                x, y = 20, int(h) - 30

            draw.text((x, y), text, fill=(0, 0, 0, 200), font=font)

            buf = io.BytesIO()
            num_img.convert("RGB").save(buf, format="PDF")
            buf.seek(0)
            num_pdf = pikepdf.open(buf)
            page.add_overlay(num_pdf.pages[0])

        pdf.save(output_path, compress_streams=True)

    return output_path


# ---- Supprimer pages ----
def delete_pages(input_path: Path, output_path: Path, pages_to_delete: str) -> Path:
    output_path = output_path.with_suffix(".pdf")
    with pikepdf.open(input_path) as pdf:
        total = len(pdf.pages)
        to_delete = set()
        for group in _parse_ranges(pages_to_delete, total):
            for p in group:
                to_delete.add(p)
        # Supprimer en ordre inverse pour ne pas décaler les indices
        for i in sorted(to_delete, reverse=True):
            if 0 <= i < total:
                del pdf.pages[i]
        pdf.save(output_path, compress_streams=True)
    return output_path


# ---- Déverrouiller PDF ----
def unlock_pdf(input_path: Path, output_path: Path, password: str = "") -> Path:
    output_path = output_path.with_suffix(".pdf")
    try:
        with pikepdf.open(input_path, password=password) as pdf:
            pdf.save(output_path, compress_streams=True)
    except pikepdf.PasswordError:
        raise ValueError("Mot de passe incorrect")
    return output_path


# ---- Protéger PDF ----
def protect_pdf(input_path: Path, output_path: Path, password: str = "") -> Path:
    output_path = output_path.with_suffix(".pdf")
    with pikepdf.open(input_path) as pdf:
        encryption = pikepdf.Encryption(
            owner=password,
            user=password,
            R=6,
        )
        pdf.save(output_path, encryption=encryption)
    return output_path
