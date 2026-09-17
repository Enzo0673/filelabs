# Sous-projet 3 — Nouveaux outils FileLabs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter 9 nouveaux outils à FileLabs en 3 groupes indépendants (PDF, Image, Media/Utils).

**Architecture:** Chaque groupe correspond à une branche git. Les fonctions métier vont dans les modules `compressors/`, les routes FastAPI dans `main.py`. Tests unitaires dans `tests/test_compressors.py`, tests endpoints dans `tests/test_endpoints.py`.

**Tech Stack:** Python 3.11, FastAPI, pikepdf, Pillow, ffmpeg-python, qrcode[pil], pyzbar, hashlib (stdlib).

---

## GROUPE 1 — PDF (`feat/sp3-pdf`)

### Task 1: Extraire images PDF — fonction

**Files:**
- Modify: `compressors/pdf/tools.py` (append à la fin)
- Test: `tests/test_compressors.py`

- [ ] **Step 1: Écrire le test qui échoue**

Dans `tests/test_compressors.py`, ajouter en bas du fichier :

```python
# ─── extract_pdf_images ────────────────────────────────────────────────────────

from compressors.pdf.tools import extract_pdf_images

def test_extract_pdf_images_pages_mode():
    """Mode pages : chaque page du PDF devient un JPEG dans un ZIP."""
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.pdf"
        out = Path(d) / "out.zip"
        inp.write_bytes(_make_pdf(2))
        result = extract_pdf_images(inp, out, mode="pages")
        assert result.exists()
        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
        assert len(names) == 2

def test_extract_pdf_images_embedded_mode():
    """Mode embedded : ZIP vide si le PDF n'a aucun XObject image."""
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.pdf"
        out = Path(d) / "out.zip"
        inp.write_bytes(_make_pdf(2))
        result = extract_pdf_images(inp, out, mode="embedded")
        assert result.exists()
        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
        assert isinstance(names, list)

def test_extract_pdf_images_invalid_mode():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.pdf"
        out = Path(d) / "out.zip"
        inp.write_bytes(_make_pdf(1))
        with pytest.raises(ValueError, match="mode"):
            extract_pdf_images(inp, out, mode="invalid")
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
py -m pytest tests/test_compressors.py::test_extract_pdf_images_pages_mode -v
```

Attendu : `ImportError` ou `AttributeError` (fonction inexistante).

- [ ] **Step 3: Implémenter `extract_pdf_images` dans `compressors/pdf/tools.py`**

Ajouter à la fin du fichier :

```python
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
            img_count = 0
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
                                # Décoder proprement en PNG via Pillow
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
                            img_count += 1
                        except Exception as e:
                            logger.debug("XObject skip: %s", e)
                            continue
                except Exception as e:
                    logger.debug("Page XObject scan skip: %s", e)
                    continue
    return output_path
```

- [ ] **Step 4: Lancer les tests**

```bash
py -m pytest tests/test_compressors.py::test_extract_pdf_images_pages_mode tests/test_compressors.py::test_extract_pdf_images_embedded_mode tests/test_compressors.py::test_extract_pdf_images_invalid_mode -v
```

Attendu : 3 PASSED (le mode pages peut SKIP si poppler absent — ajouter `pytest.importorskip("pdf2image")` si besoin).

- [ ] **Step 5: Commit**

```bash
git add compressors/pdf/tools.py tests/test_compressors.py
git commit -m "feat(pdf): extract_pdf_images (embedded + pages modes)"
```

---

### Task 2: Signature PDF — fonction

**Files:**
- Modify: `compressors/pdf/tools.py`
- Test: `tests/test_compressors.py`

- [ ] **Step 1: Écrire le test qui échoue**

```python
# ─── add_pdf_signature ─────────────────────────────────────────────────────────

from compressors.pdf.tools import add_pdf_signature

def _make_sig_png() -> bytes:
    """PNG 50x20 RGBA blanc semi-transparent."""
    img = Image.new("RGBA", (50, 20), (0, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def test_add_pdf_signature_basic():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.pdf"
        sig = Path(d) / "sig.png"
        out = Path(d) / "out.pdf"
        inp.write_bytes(_make_pdf(2))
        sig.write_bytes(_make_sig_png())
        add_pdf_signature(inp, sig, out, page=1, x=50.0, y=50.0, width=100.0)
        assert out.exists() and out.stat().st_size > 0

def test_add_pdf_signature_invalid_page():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.pdf"
        sig = Path(d) / "sig.png"
        out = Path(d) / "out.pdf"
        inp.write_bytes(_make_pdf(1))
        sig.write_bytes(_make_sig_png())
        with pytest.raises(ValueError, match="page"):
            add_pdf_signature(inp, sig, out, page=5, x=0.0, y=0.0, width=50.0)
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
py -m pytest tests/test_compressors.py::test_add_pdf_signature_basic -v
```

Attendu : `ImportError` ou `AttributeError`.

- [ ] **Step 3: Implémenter `add_pdf_signature` dans `compressors/pdf/tools.py`**

```python
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
```

- [ ] **Step 4: Lancer les tests**

```bash
py -m pytest tests/test_compressors.py::test_add_pdf_signature_basic tests/test_compressors.py::test_add_pdf_signature_invalid_page -v
```

Attendu : 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add compressors/pdf/tools.py tests/test_compressors.py
git commit -m "feat(pdf): add_pdf_signature (inject PNG onto PDF page)"
```

---

### Task 3: Routes FastAPI — Groupe PDF

**Files:**
- Modify: `main.py` (après la ligne `@app.post("/pdf/extract-text")`)
- Modify: `compressors/pdf/__init__.py`
- Test: `tests/test_endpoints.py`

- [ ] **Step 1: Exporter les nouvelles fonctions**

Lire `compressors/pdf/__init__.py`, ajouter les imports :

```python
from compressors.pdf.tools import (
    ...,  # imports existants
    extract_pdf_images,
    add_pdf_signature,
)
```

Et dans `__all__` : `"extract_pdf_images"`, `"add_pdf_signature"`.

- [ ] **Step 2: Écrire les tests endpoints qui échouent**

Dans `tests/test_endpoints.py`, ajouter :

```python
# ─── /pdf/extract-images ──────────────────────────────────────────────────────

def test_pdf_extract_images_embedded(app_client, sample_pdf_bytes):
    r = app_client.post(
        "/pdf/extract-images",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"mode": "embedded"},
    )
    assert r.status_code == 200
    assert r.json()["success"] is True

def test_pdf_extract_images_invalid_mode(app_client, sample_pdf_bytes):
    r = app_client.post(
        "/pdf/extract-images",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"mode": "invalid"},
    )
    assert r.status_code in (400, 422, 500)

# ─── /pdf/add-signature ───────────────────────────────────────────────────────

def test_pdf_add_signature(app_client, sample_pdf_bytes, sample_png_bytes):
    r = app_client.post(
        "/pdf/add-signature",
        files={
            "file": ("test.pdf", sample_pdf_bytes, "application/pdf"),
            "signature": ("sig.png", sample_png_bytes, "image/png"),
        },
        data={"page": "1", "x": "50", "y": "50", "width": "100"},
    )
    assert r.status_code == 200
    assert r.json()["success"] is True

def test_pdf_add_signature_invalid_page(app_client, sample_pdf_bytes, sample_png_bytes):
    r = app_client.post(
        "/pdf/add-signature",
        files={
            "file": ("test.pdf", sample_pdf_bytes, "application/pdf"),
            "signature": ("sig.png", sample_png_bytes, "image/png"),
        },
        data={"page": "99", "x": "50", "y": "50", "width": "100"},
    )
    assert r.status_code in (400, 500)
```

- [ ] **Step 3: Vérifier que les tests échouent**

```bash
py -m pytest tests/test_endpoints.py::test_pdf_extract_images_embedded tests/test_endpoints.py::test_pdf_add_signature -v
```

Attendu : 404 (routes inexistantes).

- [ ] **Step 4: Ajouter les imports dans `main.py`**

Trouver la ligne :
```python
from compressors.pdf import (
    compress_pdf,
    ...
    extract_pdf_text,
)
```

Ajouter `extract_pdf_images, add_pdf_signature,` à la liste.

- [ ] **Step 5: Ajouter les routes dans `main.py`**

Trouver `@app.post("/pdf/extract-text")` et ajouter après son bloc (après le `finally`) :

```python
# ---- Extraire images PDF ----
@app.post("/pdf/extract-images")
async def pdf_extract_images(
    file: UploadFile = File(...),
    mode: str = Form("embedded"),
):
    if mode not in ("embedded", "pages"):
        raise HTTPException(status_code=400, detail="mode doit être 'embedded' ou 'pages'")
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    output_path = OUTPUT_DIR / f"{uid}_output.zip"
    try:
        await _save_upload(file, input_path, MAX_SIZE["pdf"])
        extract_pdf_images(input_path, output_path, mode=mode)
        return {"success": True, "download_id": uid, "output_filename": f"images_{mode}.zip"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Signature PDF ----
@app.post("/pdf/add-signature")
async def pdf_add_signature(
    file: UploadFile = File(...),
    signature: UploadFile = File(...),
    page: int = Form(1),
    x: float = Form(50.0),
    y: float = Form(50.0),
    width: float = Form(150.0),
):
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input.pdf"
    sig_path = UPLOAD_DIR / f"{uid}_sig.png"
    output_path = OUTPUT_DIR / f"{uid}_output.pdf"
    try:
        await _save_upload(file, input_path, MAX_SIZE["pdf"])
        await _save_upload(signature, sig_path, MAX_SIZE["image"])
        add_pdf_signature(input_path, sig_path, output_path, page=page, x=x, y=y, width=width)
        stem = Path(file.filename or "doc").stem
        return {"success": True, "download_id": uid, "output_filename": f"{stem}_signed.pdf"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement")
    finally:
        input_path.unlink(missing_ok=True)
        sig_path.unlink(missing_ok=True)
```

- [ ] **Step 6: Lancer les tests**

```bash
py -m pytest tests/test_endpoints.py::test_pdf_extract_images_embedded tests/test_endpoints.py::test_pdf_extract_images_invalid_mode tests/test_endpoints.py::test_pdf_add_signature tests/test_endpoints.py::test_pdf_add_signature_invalid_page -v
```

Attendu : 4 PASSED (test_pdf_extract_images_invalid_mode : 400).

- [ ] **Step 7: Lancer la suite complète**

```bash
py -m pytest tests/ -v --tb=short
```

Attendu : tous les tests précédents toujours verts.

- [ ] **Step 8: Commit + push branche**

```bash
git checkout -b feat/sp3-pdf
git add compressors/pdf/tools.py compressors/pdf/__init__.py main.py tests/test_compressors.py tests/test_endpoints.py
git commit -m "feat(pdf): extract-images + add-signature endpoints"
git push -u origin feat/sp3-pdf
```

---

## GROUPE 2 — Image (`feat/sp3-image`)

### Task 4: Nouveau module `compressors/image/filters.py`

**Files:**
- Create: `compressors/image/filters.py`
- Modify: `compressors/image/__init__.py`
- Test: `tests/test_compressors.py`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# ─── filters image ─────────────────────────────────────────────────────────────

from compressors.image.filters import watermark_image, apply_filter, upscale_image

def test_watermark_image_text():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.jpg"
        out = Path(d) / "out.jpg"
        inp.write_bytes(_make_jpg((100, 100)))
        result = watermark_image(inp, out, text="Test", position="bottom-right", opacity=50)
        assert result.exists() and result.stat().st_size > 0

def test_watermark_image_logo():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.jpg"
        logo = Path(d) / "logo.png"
        out = Path(d) / "out.jpg"
        inp.write_bytes(_make_jpg((100, 100)))
        logo.write_bytes(_make_png((20, 20)))
        result = watermark_image(inp, out, logo_path=logo, position="center", opacity=70)
        assert result.exists() and result.stat().st_size > 0

def test_watermark_image_no_text_no_logo():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.jpg"
        out = Path(d) / "out.jpg"
        inp.write_bytes(_make_jpg())
        with pytest.raises(ValueError, match="text.*logo"):
            watermark_image(inp, out)

def test_apply_filter_grayscale():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.jpg"
        out = Path(d) / "out.jpg"
        inp.write_bytes(_make_jpg((50, 50)))
        result = apply_filter(inp, out, filter_name="grayscale")
        assert result.exists()

def test_apply_filter_sepia():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.jpg"
        out = Path(d) / "out.jpg"
        inp.write_bytes(_make_jpg((50, 50)))
        result = apply_filter(inp, out, filter_name="sepia")
        assert result.exists()

def test_apply_filter_invalid():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.jpg"
        out = Path(d) / "out.jpg"
        inp.write_bytes(_make_jpg())
        with pytest.raises(ValueError):
            apply_filter(inp, out, filter_name="oil_painting")

def test_upscale_image_2x():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.jpg"
        out = Path(d) / "out.jpg"
        inp.write_bytes(_make_jpg((100, 100)))
        result = upscale_image(inp, out, scale="2x")
        assert result.exists()
        img = Image.open(result)
        assert img.size == (200, 200)

def test_upscale_image_too_large():
    """Refuser si le résultat dépasse 50 MP."""
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.jpg"
        out = Path(d) / "out.jpg"
        # 4000x4000 * 4x = 16000x16000 = 256 MP > 50 MP
        big = Image.new("RGB", (4000, 4000), (0, 0, 0))
        buf = io.BytesIO()
        big.save(buf, format="JPEG")
        inp.write_bytes(buf.getvalue())
        with pytest.raises(ValueError, match="50"):
            upscale_image(inp, out, scale="4x")

def test_upscale_image_invalid_scale():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.jpg"
        out = Path(d) / "out.jpg"
        inp.write_bytes(_make_jpg())
        with pytest.raises(ValueError, match="scale"):
            upscale_image(inp, out, scale="5x")
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
py -m pytest tests/test_compressors.py::test_watermark_image_text -v
```

Attendu : `ModuleNotFoundError`.

- [ ] **Step 3: Créer `compressors/image/filters.py`**

```python
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
    img = Image.open(input_path)
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
```

- [ ] **Step 4: Mettre à jour `compressors/image/__init__.py`**

```python
"""Outils image : compression, conversion, recadrage, téléchargement depuis réseaux sociaux."""
from compressors.image.compress import compress_image
from compressors.image.tools import resize_image, convert_image, crop_image, rotate_image
from compressors.image.downloader import get_media_info, download_images
from compressors.image.filters import watermark_image, apply_filter, upscale_image

__all__ = [
    "compress_image",
    "resize_image", "convert_image", "crop_image", "rotate_image",
    "get_media_info", "download_images",
    "watermark_image", "apply_filter", "upscale_image",
]
```

- [ ] **Step 5: Lancer les tests**

```bash
py -m pytest tests/test_compressors.py -k "watermark or filter or upscale" -v
```

Attendu : 9 PASSED.

- [ ] **Step 6: Commit**

```bash
git add compressors/image/filters.py compressors/image/__init__.py tests/test_compressors.py
git commit -m "feat(image): watermark_image, apply_filter, upscale_image"
```

---

### Task 5: Routes FastAPI — Groupe Image

**Files:**
- Modify: `main.py`
- Test: `tests/test_endpoints.py`

- [ ] **Step 1: Écrire les tests endpoints**

```python
# ─── /image/watermark ─────────────────────────────────────────────────────────

def test_image_watermark_text(app_client, sample_jpg_bytes):
    r = app_client.post(
        "/image/watermark",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"text": "© FileLabs", "position": "bottom-right", "opacity": "50"},
    )
    assert r.status_code == 200
    assert r.json()["success"] is True

def test_image_watermark_no_text_no_logo(app_client, sample_jpg_bytes):
    r = app_client.post(
        "/image/watermark",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"opacity": "50"},
    )
    assert r.status_code in (400, 422, 500)

# ─── /image/filter ────────────────────────────────────────────────────────────

def test_image_filter_grayscale(app_client, sample_jpg_bytes):
    r = app_client.post(
        "/image/filter",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"filter": "grayscale"},
    )
    assert r.status_code == 200

def test_image_filter_sepia(app_client, sample_jpg_bytes):
    r = app_client.post(
        "/image/filter",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"filter": "sepia"},
    )
    assert r.status_code == 200

def test_image_filter_invalid(app_client, sample_jpg_bytes):
    r = app_client.post(
        "/image/filter",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"filter": "oil"},
    )
    assert r.status_code in (400, 422, 500)

# ─── /image/upscale ───────────────────────────────────────────────────────────

def test_image_upscale_2x(app_client, sample_jpg_bytes):
    r = app_client.post(
        "/image/upscale",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"scale": "2x"},
    )
    assert r.status_code == 200

def test_image_upscale_invalid_scale(app_client, sample_jpg_bytes):
    r = app_client.post(
        "/image/upscale",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"scale": "10x"},
    )
    assert r.status_code in (400, 422, 500)
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
py -m pytest tests/test_endpoints.py::test_image_watermark_text -v
```

Attendu : 404.

- [ ] **Step 3: Mettre à jour l'import dans `main.py`**

Trouver :
```python
from compressors.image import (
    compress_image,
    resize_image, convert_image, crop_image, rotate_image,
    get_media_info, download_images,
)
```

Remplacer par :
```python
from compressors.image import (
    compress_image,
    resize_image, convert_image, crop_image, rotate_image,
    get_media_info, download_images,
    watermark_image, apply_filter, upscale_image,
)
```

- [ ] **Step 4: Ajouter les routes dans `main.py`**

Trouver la dernière route `/image/` (ex: `@app.post("/image/rotate")`) et ajouter après son bloc `finally` :

```python
# ---- Filigrane image ----
@app.post("/image/watermark")
async def image_watermark(
    file: UploadFile = File(...),
    text: Optional[str] = Form(None),
    logo: Optional[UploadFile] = File(None),
    position: str = Form("bottom-right"),
    opacity: int = Form(50),
):
    if not text and not logo:
        raise HTTPException(status_code=400, detail="Fournir text ou logo")
    uid = uuid.uuid4().hex
    ext = Path(file.filename or "image.jpg").suffix.lower() or ".jpg"
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    logo_path = None
    output_path = OUTPUT_DIR / f"{uid}_output{ext}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["image"])
        if logo:
            logo_path = UPLOAD_DIR / f"{uid}_logo.png"
            await _save_upload(logo, logo_path, MAX_SIZE["image"])
        watermark_image(input_path, output_path, text=text, logo_path=logo_path, position=position, opacity=opacity)
        stem = Path(file.filename or "image").stem
        return {"success": True, "download_id": uid, "output_filename": f"{stem}_watermarked{ext}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement")
    finally:
        input_path.unlink(missing_ok=True)
        if logo_path:
            logo_path.unlink(missing_ok=True)


# ---- Filtre image (N&B / Sépia) ----
@app.post("/image/filter")
async def image_filter(
    file: UploadFile = File(...),
    filter: str = Form(...),
):
    if filter not in ("grayscale", "sepia"):
        raise HTTPException(status_code=400, detail="filter doit être 'grayscale' ou 'sepia'")
    uid = uuid.uuid4().hex
    ext = Path(file.filename or "image.jpg").suffix.lower() or ".jpg"
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    output_path = OUTPUT_DIR / f"{uid}_output{ext}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["image"])
        apply_filter(input_path, output_path, filter_name=filter)
        stem = Path(file.filename or "image").stem
        return {"success": True, "download_id": uid, "output_filename": f"{stem}_{filter}{ext}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Agrandir image ----
@app.post("/image/upscale")
async def image_upscale(
    file: UploadFile = File(...),
    scale: str = Form("2x"),
):
    if scale not in ("2x", "3x", "4x"):
        raise HTTPException(status_code=400, detail="scale doit être 2x, 3x ou 4x")
    uid = uuid.uuid4().hex
    ext = Path(file.filename or "image.jpg").suffix.lower() or ".jpg"
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    output_path = OUTPUT_DIR / f"{uid}_output{ext}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["image"])
        upscale_image(input_path, output_path, scale=scale)
        stem = Path(file.filename or "image").stem
        return {"success": True, "download_id": uid, "output_filename": f"{stem}_{scale}{ext}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors du traitement")
    finally:
        input_path.unlink(missing_ok=True)
```

Ajouter aussi `from typing import Optional` si pas déjà présent (vérifier ligne 1-30 de main.py — il y a déjà `from typing import List`, donc ajouter `Optional` à cet import).

- [ ] **Step 5: Lancer les tests**

```bash
py -m pytest tests/test_endpoints.py -k "watermark or filter or upscale" -v
```

Attendu : 7 PASSED.

- [ ] **Step 6: Suite complète**

```bash
py -m pytest tests/ -v --tb=short
```

- [ ] **Step 7: Commit + push branche**

```bash
git checkout -b feat/sp3-image
git add compressors/image/filters.py compressors/image/__init__.py main.py tests/test_compressors.py tests/test_endpoints.py
git commit -m "feat(image): watermark, filtre N&B/sépia, upscale endpoints"
git push -u origin feat/sp3-image
```

---

## GROUPE 3 — Media & Utils (`feat/sp3-media-utils`)

### Task 6: Extraire audio + Thumbnails vidéo — fonctions

**Files:**
- Modify: `compressors/media/video.py`
- Test: `tests/test_compressors.py`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# ─── extract_audio ────────────────────────────────────────────────────────────

from compressors.media.video import extract_audio, extract_thumbnails

def test_extract_audio_invalid_format():
    """Format invalide doit lever ValueError avant d'appeler ffmpeg."""
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.mp4"
        out = Path(d) / "out.xyz"
        inp.write_bytes(b"\x00" * 100)
        with pytest.raises(ValueError, match="format"):
            extract_audio(inp, out, fmt="xyz")

def test_extract_thumbnails_invalid_count():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.mp4"
        out_dir = Path(d) / "thumbs"
        inp.write_bytes(b"\x00" * 100)
        with pytest.raises(ValueError, match="count"):
            extract_thumbnails(inp, out_dir, count=0)

def test_extract_thumbnails_count_too_high():
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "in.mp4"
        out_dir = Path(d) / "thumbs"
        inp.write_bytes(b"\x00" * 100)
        with pytest.raises(ValueError, match="count"):
            extract_thumbnails(inp, out_dir, count=11)
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
py -m pytest tests/test_compressors.py::test_extract_audio_invalid_format -v
```

Attendu : `ImportError`.

- [ ] **Step 3: Ajouter les fonctions dans `compressors/media/video.py`**

Ajouter à la fin du fichier :

```python
# ---- Extraire audio ----
def extract_audio(input_path: Path, output_path: Path, fmt: str = "mp3") -> Path:
    """Extrait la piste audio d'une vidéo. fmt : 'mp3' ou 'wav'."""
    if fmt not in ("mp3", "wav"):
        raise ValueError(f"format invalide : {fmt!r} (attendu 'mp3' ou 'wav')")

    output_path = output_path.with_suffix(f".{fmt}")
    ffmpeg_bin = _find_ffmpeg()

    codec = "libmp3lame" if fmt == "mp3" else "pcm_s16le"
    cmd = [ffmpeg_bin, "-y", "-i", str(input_path), "-vn", "-acodec", codec, str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error: {result.stderr[-500:]}")
    return output_path


# ---- Thumbnails vidéo ----
def extract_thumbnails(input_path: Path, output_dir: Path, count: int = 5) -> Path:
    """
    Capture `count` frames réparties dans la vidéo.
    Retourne un ZIP des JPEG dans output_dir.parent / <stem>.zip.
    """
    if count < 1 or count > 10:
        raise ValueError(f"count invalide : {count} (attendu 1-10)")

    output_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = _find_ffmpeg()

    # Probe durée
    probe_cmd = [
        ffmpeg_bin, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(input_path),
    ]
    # ffprobe si disponible, sinon ffmpeg -i
    ffprobe_bin = shutil.which("ffprobe") or ffmpeg_bin.replace("ffmpeg", "ffprobe")
    if Path(ffprobe_bin).exists() or shutil.which(ffprobe_bin):
        probe_cmd[0] = ffprobe_bin
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    try:
        duration = float(result.stdout.strip())
    except ValueError:
        duration = 60.0  # fallback

    interval = max(1, duration / (count + 1))

    for i in range(count):
        t = interval * (i + 1)
        out_file = output_dir / f"thumb_{i+1:02d}.jpg"
        cmd = [
            ffmpeg_bin, "-y", "-ss", str(t), "-i", str(input_path),
            "-frames:v", "1", "-q:v", "2", str(out_file),
        ]
        subprocess.run(cmd, capture_output=True)

    zip_path = output_dir.parent / f"{input_path.stem}_thumbnails.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(output_dir.glob("*.jpg")):
            zf.write(f, f.name)
    return zip_path
```

Ajouter aussi `import zipfile` en haut si absent (vérifier — probablement absent de video.py, à ajouter).

- [ ] **Step 4: Lancer les tests**

```bash
py -m pytest tests/test_compressors.py::test_extract_audio_invalid_format tests/test_compressors.py::test_extract_thumbnails_invalid_count tests/test_compressors.py::test_extract_thumbnails_count_too_high -v
```

Attendu : 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add compressors/media/video.py tests/test_compressors.py
git commit -m "feat(media): extract_audio, extract_thumbnails"
```

---

### Task 7: QR Code — nouveau module

**Files:**
- Create: `compressors/qr.py`
- Modify: `requirements.txt`, `Dockerfile`
- Test: `tests/test_compressors.py`

- [ ] **Step 1: Installer les dépendances**

```bash
py -m pip install "qrcode[pil]" pyzbar
```

- [ ] **Step 2: Écrire les tests qui échouent**

```python
# ─── QR Code ──────────────────────────────────────────────────────────────────

from compressors.qr import generate_qr, read_qr

def test_generate_qr_basic():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "qr.png"
        result = generate_qr("https://filelabs.onrender.com", out)
        assert result.exists() and result.stat().st_size > 0

def test_generate_qr_empty_text():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "qr.png"
        with pytest.raises(ValueError, match="vide"):
            generate_qr("", out)

def test_read_qr_roundtrip():
    """Générer puis lire le QR doit retourner le texte original."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "qr.png"
        text = "FileLabs test QR"
        generate_qr(text, out)
        result = read_qr(out)
        assert result["data"] == text

def test_read_qr_no_code():
    """Une image sans QR doit retourner data=None ou lever ValueError."""
    with tempfile.TemporaryDirectory() as d:
        img_path = Path(d) / "blank.png"
        img_path.write_bytes(_make_png((100, 100)))
        result = read_qr(img_path)
        assert result.get("data") is None
```

- [ ] **Step 3: Vérifier que les tests échouent**

```bash
py -m pytest tests/test_compressors.py::test_generate_qr_basic -v
```

Attendu : `ModuleNotFoundError`.

- [ ] **Step 4: Créer `compressors/qr.py`**

```python
"""
QR Code — génération et lecture
Dépendances : qrcode[pil], pyzbar
"""

from pathlib import Path
from typing import Optional


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
```

- [ ] **Step 5: Mettre à jour `requirements.txt`**

Ajouter à la fin (avant la section commentée dev/tests) :

```
# QR Code
qrcode[pil]>=7.4.2
pyzbar>=0.1.9
```

- [ ] **Step 6: Mettre à jour `Dockerfile`**

Trouver :
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    poppler-utils \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*
```

Remplacer par :
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    poppler-utils \
    libreoffice \
    libzbar0 \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 7: Lancer les tests**

```bash
py -m pytest tests/test_compressors.py -k "qr" -v
```

Attendu : 4 PASSED (test_read_qr_no_code peut dépendre de libzbar présent).

- [ ] **Step 8: Commit**

```bash
git add compressors/qr.py requirements.txt Dockerfile tests/test_compressors.py
git commit -m "feat(qr): generate_qr, read_qr + deps (qrcode, pyzbar)"
```

---

### Task 8: Hasher fichier — route inline

**Files:**
- Modify: `main.py`
- Test: `tests/test_endpoints.py`

- [ ] **Step 1: Écrire les tests endpoints**

```python
# ─── /utils/hash ──────────────────────────────────────────────────────────────

def test_utils_hash_default(app_client, sample_jpg_bytes):
    r = app_client.post(
        "/utils/hash",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
    )
    assert r.status_code == 200
    data = r.json()
    assert "md5" in data
    assert "sha256" in data
    assert len(data["md5"]) == 32
    assert len(data["sha256"]) == 64

def test_utils_hash_sha512(app_client, sample_jpg_bytes):
    r = app_client.post(
        "/utils/hash",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"algorithms": "sha512"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "sha512" in data
    assert len(data["sha512"]) == 128

def test_utils_hash_invalid_algo(app_client, sample_jpg_bytes):
    r = app_client.post(
        "/utils/hash",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"algorithms": "md2"},
    )
    assert r.status_code in (400, 422)
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
py -m pytest tests/test_endpoints.py::test_utils_hash_default -v
```

Attendu : 404.

- [ ] **Step 3: Ajouter la route dans `main.py`**

Trouver la route `@app.delete("/cleanup/{uid}")` et ajouter avant :

```python
# ---- Hasher fichier ----
_VALID_HASH_ALGOS = {"md5", "sha256", "sha512"}

@app.post("/utils/hash")
async def utils_hash(
    file: UploadFile = File(...),
    algorithms: str = Form("md5,sha256"),
):
    algo_list = [a.strip().lower() for a in algorithms.split(",") if a.strip()]
    invalid = [a for a in algo_list if a not in _VALID_HASH_ALGOS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Algorithme(s) non supporté(s) : {invalid}")
    if not algo_list:
        algo_list = ["md5", "sha256"]

    content = await file.read()
    result = {}
    for algo in algo_list:
        result[algo] = hashlib.new(algo, content).hexdigest()
    return result
```

Note : `hashlib` est déjà importé en haut de `main.py` (ligne 13).

- [ ] **Step 4: Lancer les tests**

```bash
py -m pytest tests/test_endpoints.py -k "hash" -v
```

Attendu : 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_endpoints.py
git commit -m "feat(utils): /utils/hash endpoint (md5/sha256/sha512)"
```

---

### Task 9: Routes FastAPI — QR Code + Audio + Thumbnails

**Files:**
- Modify: `main.py`
- Test: `tests/test_endpoints.py`

- [ ] **Step 1: Écrire les tests endpoints**

```python
# ─── /qr/ ─────────────────────────────────────────────────────────────────────

def test_qr_generate(app_client):
    r = app_client.post("/qr/generate", data={"text": "https://filelabs.onrender.com"})
    assert r.status_code == 200
    assert r.json()["success"] is True

def test_qr_generate_empty_text(app_client):
    r = app_client.post("/qr/generate", data={"text": ""})
    assert r.status_code in (400, 422)

def test_qr_read(app_client, sample_png_bytes):
    # PNG blanc sans QR — doit retourner data null ou 200 avec data=None
    r = app_client.post(
        "/qr/read",
        files={"file": ("test.png", sample_png_bytes, "image/png")},
    )
    assert r.status_code == 200
    assert "data" in r.json()

# ─── /video/extract-audio ─────────────────────────────────────────────────────

def test_video_extract_audio_invalid_format(app_client, sample_jpg_bytes):
    r = app_client.post(
        "/video/extract-audio",
        files={"file": ("test.mp4", sample_jpg_bytes, "video/mp4")},
        data={"format": "xyz"},
    )
    assert r.status_code in (400, 422)

# ─── /video/thumbnails ────────────────────────────────────────────────────────

def test_video_thumbnails_invalid_count(app_client, sample_jpg_bytes):
    r = app_client.post(
        "/video/thumbnails",
        files={"file": ("test.mp4", sample_jpg_bytes, "video/mp4")},
        data={"count": "0"},
    )
    assert r.status_code in (400, 422)
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
py -m pytest tests/test_endpoints.py::test_qr_generate tests/test_endpoints.py::test_video_extract_audio_invalid_format -v
```

Attendu : 404 ou 422.

- [ ] **Step 3: Ajouter les imports dans `main.py`**

Après les imports `compressors.media` existants, ajouter :

```python
from compressors.qr import generate_qr, read_qr
from compressors.media.video import extract_audio, extract_thumbnails
```

- [ ] **Step 4: Ajouter les routes QR dans `main.py`**

Ajouter avant `@app.delete("/cleanup/{uid}")` :

```python
# ---- QR Code — Générer ----
@app.post("/qr/generate")
async def qr_generate(text: str = Form(...)):
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Le texte ne peut pas être vide")
    uid = uuid.uuid4().hex
    output_path = OUTPUT_DIR / f"{uid}_output.png"
    try:
        generate_qr(text.strip(), output_path)
        return {"success": True, "download_id": uid, "output_filename": "qrcode.png"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de la génération du QR")


# ---- QR Code — Lire ----
@app.post("/qr/read")
async def qr_read(file: UploadFile = File(...)):
    uid = uuid.uuid4().hex
    ext = Path(file.filename or "image.png").suffix.lower() or ".png"
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["image"])
        result = read_qr(input_path)
        return result
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de la lecture du QR")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Extraire audio ----
@app.post("/video/extract-audio")
async def video_extract_audio(
    file: UploadFile = File(...),
    format: str = Form("mp3"),
):
    if format not in ("mp3", "wav"):
        raise HTTPException(status_code=400, detail="format doit être 'mp3' ou 'wav'")
    uid = uuid.uuid4().hex
    ext = Path(file.filename or "video.mp4").suffix.lower() or ".mp4"
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    output_path = OUTPUT_DIR / f"{uid}_output.{format}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["video"])
        extract_audio(input_path, output_path, fmt=format)
        stem = Path(file.filename or "video").stem
        return {"success": True, "download_id": uid, "output_filename": f"{stem}_audio.{format}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de l'extraction audio")
    finally:
        input_path.unlink(missing_ok=True)


# ---- Thumbnails vidéo ----
@app.post("/video/thumbnails")
async def video_thumbnails(
    file: UploadFile = File(...),
    count: int = Form(5),
):
    if count < 1 or count > 10:
        raise HTTPException(status_code=400, detail="count doit être entre 1 et 10")
    uid = uuid.uuid4().hex
    ext = Path(file.filename or "video.mp4").suffix.lower() or ".mp4"
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    output_dir = OUTPUT_DIR / f"{uid}_thumbs"
    try:
        await _save_upload(file, input_path, MAX_SIZE["video"])
        zip_path = extract_thumbnails(input_path, output_dir, count=count)
        final_path = OUTPUT_DIR / f"{uid}_output.zip"
        zip_path.rename(final_path)
        return {"success": True, "download_id": uid, "output_filename": "thumbnails.zip"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de l'extraction des thumbnails")
    finally:
        input_path.unlink(missing_ok=True)
        shutil.rmtree(output_dir, ignore_errors=True)
```

- [ ] **Step 5: Mettre à jour `_PROCESSING_PATHS` dans `main.py`**

Trouver :
```python
_PROCESSING_PATHS = ("/compress", "/pdf/", "/image/", "/video/", "/download/", "/media/")
```

Remplacer par :
```python
_PROCESSING_PATHS = ("/compress", "/pdf/", "/image/", "/video/", "/download/", "/media/", "/qr/", "/utils/")
```

- [ ] **Step 6: Lancer les tests**

```bash
py -m pytest tests/test_endpoints.py -k "qr or extract_audio or thumbnails or hash" -v
```

Attendu : tous PASSED.

- [ ] **Step 7: Suite complète**

```bash
py -m pytest tests/ -v --tb=short
```

Attendu : tous les tests précédents toujours verts.

- [ ] **Step 8: Commit + push branche**

```bash
git checkout -b feat/sp3-media-utils
git add compressors/qr.py compressors/media/video.py main.py requirements.txt Dockerfile tests/test_compressors.py tests/test_endpoints.py
git commit -m "feat(media-utils): extract-audio, thumbnails, hash, QR Code endpoints"
git push -u origin feat/sp3-media-utils
```

---

## Récapitulatif des branches

| Branche | Outils | Nouvelles deps |
|---------|--------|----------------|
| `feat/sp3-pdf` | extract-images, add-signature | aucune |
| `feat/sp3-image` | watermark, filter, upscale | aucune (Pillow déjà présent) |
| `feat/sp3-media-utils` | extract-audio, thumbnails, hash, QR | `qrcode[pil]`, `pyzbar`, `libzbar0` |
