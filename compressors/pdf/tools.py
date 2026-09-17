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
- Réparer PDF (reconstruire structure, pages vides, annotations aplaties)
"""

from pathlib import Path
from typing import List
import pikepdf
from PIL import Image
import io
import zipfile
import re
import logging

logger = logging.getLogger(__name__)


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
    try:
        groups = []
        for part in ranges_str.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                a, b = int(a), int(b)
                if a < 1 or b < a or b > total:
                    raise ValueError(f"Plage invalide : {a}-{b} (total={total})")
                groups.append(list(range(a - 1, b)))
            else:
                p = int(part)
                if p < 1 or p > total:
                    raise ValueError(f"Page invalide : {p} (total={total})")
                groups.append([p - 1])
        return groups
    except ValueError:
        raise
    except Exception:
        raise ValueError("Format de plages invalide")


# ---- PDF vers JPG ----
def pdf_to_jpg(input_path: Path, output_path: Path, dpi: int = 150) -> Path:
    """Convertit chaque page en JPG, retourne un ZIP. Streaming page par page."""
    from pdf2image import convert_from_path
    import os
    zip_path = output_path.with_suffix(".zip")
    thread_count = os.cpu_count() or 2
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, img in enumerate(convert_from_path(
            str(input_path), dpi=dpi, thread_count=thread_count,
        )):
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            zf.writestr(f"page_{i+1:03d}.jpg", buf.getvalue())
            img.close()
    return zip_path


# ---- JPG vers PDF ----
def jpg_to_pdf(input_paths: List[Path], output_path: Path) -> Path:
    output_path = output_path.with_suffix(".pdf")
    images = []
    try:
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
    finally:
        for img in images:
            try:
                img.close()
            except Exception:
                pass
    return output_path


_VALID_ANGLES = {0, 90, 180, 270}


# ---- Rotation PDF par map individuelle ----
def rotate_pdf_map(input_path: Path, output_path: Path, rotation_map: str) -> Path:
    """rotation_map = '1:90,3:180,5:270' (pages 1-indexées)"""
    output_path = output_path.with_suffix(".pdf")
    try:
        mapping = {}
        for entry in rotation_map.split(','):
            entry = entry.strip()
            if ':' in entry:
                pg, angle = entry.split(':', 1)
                angle_int = int(angle)
                if angle_int not in _VALID_ANGLES:
                    raise ValueError(f"Angle invalide : {angle_int}. Valeurs acceptées : 0, 90, 180, 270")
                mapping[int(pg) - 1] = angle_int

        with pikepdf.open(input_path) as pdf:
            for idx, angle in mapping.items():
                if 0 <= idx < len(pdf.pages):
                    page = pdf.pages[idx]
                    current = int(page.get("/Rotate", 0))
                    page["/Rotate"] = (current + angle) % 360
            pdf.save(output_path, compress_streams=True)
    except ValueError:
        raise
    except Exception:
        raise ValueError("Erreur lors de la rotation du PDF")
    return output_path


# ---- Rotation PDF ----
def rotate_pdf(input_path: Path, output_path: Path, angle: int = 90, pages: str = "all") -> Path:
    output_path = output_path.with_suffix(".pdf")
    with pikepdf.open(input_path) as pdf:
        total = len(pdf.pages)
        if pages == "all":
            target_pages = list(range(total))
        else:
            target_pages = [p-1 for group in _parse_ranges(pages, total) for p in group]

        for i in target_pages:
            if 0 <= i < total:
                page = pdf.pages[i]
                current = int(page.get("/Rotate", 0))
                page["/Rotate"] = (current + angle) % 360

        pdf.save(output_path, compress_streams=True)
    return output_path


# ---- Filigrane PDF ----
def watermark_pdf(input_path: Path, output_path: Path, text: str = "CONFIDENTIEL", opacity: float = 0.3, position: str = "diagonal", color: str = "gray") -> Path:
    output_path = output_path.with_suffix(".pdf")
    # Sanitize text: truncate, strip control characters, escape PDF string delimiters
    text = text[:200]
    # Remove all control characters (< 0x20) including \n, \r which could break the PDF content stream
    text = "".join(c for c in text if ord(c) >= 0x20)
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    # Couleur : convertir la sélection en composantes RGB [0..1]
    _COLOR_MAP = {
        "gray":  (0.5, 0.5, 0.5),
        "black": (0.0, 0.0, 0.0),
        "red":   (0.8, 0.1, 0.1),
        "blue":  (0.1, 0.2, 0.8),
    }
    rc, gc, bc = _COLOR_MAP.get(color, (0.5, 0.5, 0.5))
    # Simuler l'opacité en mélangeant avec le blanc (PDF texte n'a pas d'alpha natif)
    r = rc + (1.0 - rc) * (1.0 - opacity)
    g = gc + (1.0 - gc) * (1.0 - opacity)
    b = bc + (1.0 - bc) * (1.0 - opacity)

    with pikepdf.open(input_path) as pdf:
        for page in pdf.pages:
            mediabox = page.mediabox
            w = float(mediabox[2])
            h = float(mediabox[3])
            cx = w / 2
            cy = h / 2

            if position == "diagonal":
                transform = f"-0.5 0.866 -0.866 -0.5 {cx:.1f} {cy:.1f} Tm\n"
            elif position == "horizontal":
                transform = f"1 0 0 1 {cx:.1f} {cy:.1f} Tm\n"
            elif position == "top":
                transform = f"1 0 0 1 {cx:.1f} {h * 0.85:.1f} Tm\n"
            elif position == "bottom":
                transform = f"1 0 0 1 {cx:.1f} {h * 0.10:.1f} Tm\n"
            else:
                transform = f"-0.5 0.866 -0.866 -0.5 {cx:.1f} {cy:.1f} Tm\n"

            watermark_stream = (
                f"q\n"
                f"{r:.3f} {g:.3f} {b:.3f} rg\n"
                f"BT\n"
                f"/Helvetica 48 Tf\n"
                f"{r:.3f} {g:.3f} {b:.3f} rg\n"
                f"{transform}"
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
            mediabox = page.mediabox
            w = float(mediabox[2])
            h = float(mediabox[3])

            text = f"{i+1} / {total}"
            # Estimation largeur texte : ~7pt par caractère à taille 12
            tw = len(text) * 7

            if position == "bottom-center":
                tx = (w - tw) / 2
                ty = 20
            elif position == "bottom-right":
                tx = w - tw - 20
                ty = 20
            else:  # bottom-left
                tx = 20
                ty = 20

            # PDF brut : texte direct, sans image
            num_stream = (
                f"q\n"
                f"0 0 0 rg\n"
                f"BT\n"
                f"/Helvetica 12 Tf\n"
                f"{tx:.1f} {ty:.1f} Td\n"
                f"({text}) Tj\n"
                f"ET\n"
                f"Q\n"
            ).encode()

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

            num_stream_obj = pikepdf.Stream(pdf, num_stream)
            existing = page.get("/Contents")
            if existing is None:
                page["/Contents"] = num_stream_obj
            elif isinstance(existing, pikepdf.Array):
                existing.append(num_stream_obj)
                page["/Contents"] = existing
            else:
                page["/Contents"] = pikepdf.Array([existing, num_stream_obj])

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


# ---- Réparer PDF ----
def repair_pdf(
    input_path: Path,
    output_path: Path,
    remove_blank_pages: bool = False,
    flatten_annotations: bool = False,
) -> dict:
    """
    Répare un PDF :
    - Reconstruit la structure (re-sérialisation pikepdf)
    - Optionnel : supprime les pages visuellement vides
    - Optionnel : aplatit les annotations/formulaires dans le contenu

    Retourne {"output": Path, "removed_pages": int, "annotations_flattened": bool}
    """
    output_path = output_path.with_suffix(".pdf")

    try:
        pdf = pikepdf.open(input_path, suppress_warnings=True)
    except Exception:
        # Tentative de récupération en mode permissif
        pdf = pikepdf.open(input_path, suppress_warnings=True, password="")

    removed = 0

    with pdf:
        total = len(pdf.pages)

        # ---- Aplatir les annotations ----
        if flatten_annotations:
            for page in pdf.pages:
                if "/Annots" in page:
                    annots = page["/Annots"]
                    # Construire un stream de contenu pour chaque annotation visible
                    flattened_streams = []
                    for annot in annots:
                        try:
                            annot_obj = annot
                            # Récupérer l'apparence normale (/AP /N)
                            if "/AP" in annot_obj and "/N" in annot_obj["/AP"]:
                                ap = annot_obj["/AP"]["/N"]
                                # Récupérer la position (/Rect)
                                if "/Rect" in annot_obj:
                                    rect = annot_obj["/Rect"]
                                    x1, y1, x2, y2 = (float(v) for v in rect)
                                    # Écrire l'apparence à la bonne position
                                    name = f"/Annot{len(flattened_streams)}"
                                    if "/Resources" not in page:
                                        page["/Resources"] = pikepdf.Dictionary()
                                    res = page["/Resources"]
                                    if "/XObject" not in res:
                                        res["/XObject"] = pikepdf.Dictionary()
                                    res["/XObject"][name] = ap
                                    stream_data = (
                                        f"q {x1:.2f} {y1:.2f} {x2-x1:.2f} {y2-y1:.2f} re W n "
                                        f"{x1:.2f} {y1:.2f} cm {name} Do Q\n"
                                    ).encode()
                                    flattened_streams.append(pikepdf.Stream(pdf, stream_data))
                        except Exception as e:
                            logger.debug("Annotation flatten skip: %s", e)
                            continue
                    del page["/Annots"]
                    # Ajouter les streams aplatis
                    if flattened_streams:
                        existing = page.get("/Contents")
                        if existing is None:
                            page["/Contents"] = pikepdf.Array(flattened_streams)
                        elif isinstance(existing, pikepdf.Array):
                            existing.extend(flattened_streams)
                            page["/Contents"] = existing
                        else:
                            page["/Contents"] = pikepdf.Array([existing] + flattened_streams)

        # ---- Supprimer les pages vides ----
        if remove_blank_pages:
            to_remove = []
            for i, page in enumerate(pdf.pages):
                if _is_blank_page(page):
                    to_remove.append(i)
            for i in sorted(to_remove, reverse=True):
                del pdf.pages[i]
            removed = len(to_remove)

        # ---- Reconstruire la structure (re-sérialisation) ----
        pdf.save(
            output_path,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )

    with pikepdf.open(output_path) as _check:
        pages_remaining = len(_check.pages)
    return {
        "output": output_path,
        "removed_pages": removed,
        "pages_remaining": pages_remaining,
        "annotations_flattened": flatten_annotations,
    }


def _is_blank_page(page) -> bool:
    """Retourne True si la page semble visuellement vide."""
    try:
        # Page sans /Contents
        if "/Contents" not in page:
            return True
        contents = page["/Contents"]
        # Récupérer les données du stream
        if isinstance(contents, pikepdf.Array):
            data = b"".join(s.read_bytes() for s in contents)
        else:
            data = contents.read_bytes()
        # Nettoyer les opérateurs PDF triviaux (save/restore, matrix, etc.)
        stripped = re.sub(
            rb'\s*(q|Q|cm|w|J|j|M|d|ri|i|gs|W|n)\s*', b'', data
        ).strip()
        return len(stripped) == 0
    except Exception as e:
        logger.debug("Blank page detection fallback: %s", e)
        return False


# ---- Extraire texte PDF ----

def extract_pdf_text(input_path: str) -> dict:
    """
    Extrait le texte d'un PDF natif (avec couche texte).
    Retourne le texte par page + détection PDF scanné.
    """
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer, LTPage

    pages_text = []
    total_chars = 0

    try:
        for page_layout in extract_pages(input_path):
            page_text = []
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    t = element.get_text()
                    page_text.append(t)
                    total_chars += len(t.strip())
            pages_text.append("".join(page_text).strip())
    except Exception as e:
        raise ValueError(f"Impossible de lire le PDF : {e}")

    is_scanned = total_chars < 50
    return {
        "pages": pages_text,
        "page_count": len(pages_text),
        "total_chars": total_chars,
        "is_scanned": is_scanned,
    }


# ---- Extraire images PDF ----
def extract_pdf_images(input_path: Path, output_path: Path, mode: str = "embedded") -> Path:
    """
    mode='embedded' : extrait les XObjects Image (PNG/JPEG) de chaque page.
    mode='pages'    : convertit chaque page en JPEG via pdf2image.
    Retourne un ZIP.
    """
    if mode not in ("embedded", "pages"):
        raise ValueError(f"mode invalide : {mode!r} (attendu 'embedded' ou 'pages')")

    output_path = output_path.with_suffix(".zip")

    if mode == "pages":
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError("pdf2image requis pour le mode 'pages' (pip install pdf2image)")
        images = convert_from_path(str(input_path), fmt="jpeg", dpi=150)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, img in enumerate(images):
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                zf.writestr(f"page_{i+1:03d}.jpg", buf.getvalue())
        return output_path

    # mode == "embedded"
    with pikepdf.open(input_path) as pdf:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    resources = page.get("/Resources")
                    if resources is None:
                        continue
                    xobjects = resources.get("/XObject")
                    if xobjects is None:
                        continue
                    for name, xobj in xobjects.items():
                        try:
                            if xobj.get("/Subtype") != "/Image":
                                continue
                            raw = xobj.read_raw_bytes()
                            filters = xobj.get("/Filter")
                            ext = ".jpg" if str(filters) in ("/DCTDecode", "[/DCTDecode]") else ".png"
                            if ext == ".png":
                                w = int(xobj["/Width"])
                                h = int(xobj["/Height"])
                                cs = str(xobj.get("/ColorSpace", "/DeviceRGB"))
                                mode_pil = "L" if "Gray" in cs else "RGB"
                                try:
                                    data = xobj.read_bytes()
                                    img_pil = Image.frombytes(mode_pil, (w, h), data)
                                    buf = io.BytesIO()
                                    img_pil.save(buf, format="PNG")
                                    raw = buf.getvalue()
                                except Exception as e:
                                    logger.debug("XObject PNG decode skip: %s", e)
                                    continue
                            fname = f"page{page_num+1:03d}_{name.lstrip('/')}{ext}"
                            zf.writestr(fname, raw)
                        except Exception as e:
                            logger.debug("XObject skip: %s", e)
                            continue
                except Exception as e:
                    logger.debug("Page XObject scan skip: %s", e)
    return output_path


# ---- Signature PDF ----
def add_pdf_signature(
    input_path: Path,
    signature_path: Path,
    output_path: Path,
    page: int = 1,
    x: float = 50.0,
    y: float = 50.0,
    width: float = 150.0,
) -> Path:
    """
    Injecte une image PNG comme signature sur la page `page` (1-indexé).
    x, y : position en bas-gauche (points PDF, origine bas-gauche de la page).
    width : largeur en points PDF (hauteur calculée proportionnellement).
    """
    output_path = output_path.with_suffix(".pdf")

    # Charger la signature et calculer hauteur proportionnelle
    sig_img = Image.open(signature_path).convert("RGBA")
    aspect = sig_img.height / sig_img.width
    height = width * aspect

    # Encoder la signature en JPEG (fond blanc pour les canaux alpha)
    bg = Image.new("RGB", sig_img.size, (255, 255, 255))
    bg.paste(sig_img, mask=sig_img.split()[3])
    buf = io.BytesIO()
    bg.save(buf, format="JPEG", quality=90)
    jpeg_bytes = buf.getvalue()

    with pikepdf.open(input_path) as pdf:
        total = len(pdf.pages)
        if page < 1 or page > total:
            raise ValueError(f"page {page} invalide (PDF a {total} pages)")

        target_page = pdf.pages[page - 1]

        # Créer le stream image JPEG comme XObject
        sig_xobj = pikepdf.Stream(pdf, jpeg_bytes)
        sig_xobj["/Type"] = pikepdf.Name("/XObject")
        sig_xobj["/Subtype"] = pikepdf.Name("/Image")
        sig_xobj["/Filter"] = pikepdf.Name("/DCTDecode")
        sig_xobj["/ColorSpace"] = pikepdf.Name("/DeviceRGB")
        sig_xobj["/BitsPerComponent"] = pikepdf.Integer(8)
        sig_xobj["/Width"] = pikepdf.Integer(sig_img.width)
        sig_xobj["/Height"] = pikepdf.Integer(sig_img.height)

        # Injecter dans les ressources de la page
        if "/Resources" not in target_page:
            target_page["/Resources"] = pikepdf.Dictionary()
        resources = target_page["/Resources"]
        if "/XObject" not in resources:
            resources["/XObject"] = pikepdf.Dictionary()

        xobj_name = "/Sig0"
        resources["/XObject"][xobj_name] = sig_xobj

        # Ajouter le stream de contenu pour afficher l'image
        content_stream = f"q {width:.2f} 0 0 {height:.2f} {x:.2f} {y:.2f} cm {xobj_name} Do Q"
        existing = target_page.get("/Contents")
        new_stream = pikepdf.Stream(pdf, content_stream.encode())
        if existing is None:
            target_page["/Contents"] = new_stream
        elif isinstance(existing, pikepdf.Array):
            existing.append(new_stream)
        else:
            target_page["/Contents"] = pikepdf.Array([existing, new_stream])

        pdf.save(output_path, compress_streams=True)

    return output_path
