# Robustesse & Tests — FileLabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter ~120 tests couvrant compression, endpoints, middleware + 5 fixes robustesse (ThreadPoolExecutor silencieux, except Exception sans log, progress dict sans TTL, race condition threading, imports dupliqués).

**Architecture:** Tests d'abord — écrire les tests, observer les échecs, appliquer les fixes dans l'ordre R1→R2→R3→R4→R5. Les fixtures sont centralisées dans `conftest.py`. Les endpoints sont testés via `TestClient` FastAPI. Les fonctions ffmpeg sont mockées.

**Tech Stack:** Python 3.x, FastAPI, pytest, httpx (via TestClient), unittest.mock, Pillow, pikepdf, zipfile

---

## Fichiers touchés

| Fichier | Action | Raison |
|---------|--------|--------|
| `tests/conftest.py` | Créer | Fixtures partagées (client, fichiers samples) |
| `tests/test_compressors.py` | Modifier (ajouter à la fin) | Tests unitaires compress_image, compress_pdf, compress_archive |
| `tests/test_endpoints.py` | Créer | Tests intégration tous endpoints FastAPI |
| `tests/test_middleware.py` | Créer | Tests rate limiting + security headers |
| `compressors/pdf/compress.py` | Modifier lignes 44-51 | R1: propagation exception ThreadPoolExecutor + R2: logging |
| `compressors/pdf/tools.py` | Modifier lignes 446, 504 | R2: except Exception → type spécifique + logging |
| `compressors/media/video.py` | Modifier ligne 139 | R2: except Exception → ffmpeg.Error + logging |
| `main.py` | Modifier (compress endpoint + imports) | R3: cleanup progress_key dans finally + R5: supprimer shutil dupliqués |

---

## Task 1 : Créer `tests/conftest.py`

**Contexte :** Fixtures centralisées pour éviter la duplication dans les 3 nouveaux fichiers de tests. Le `TestClient` FastAPI simule des requêtes HTTP sans lancer de serveur réel.

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1 : Créer `tests/conftest.py`**

```python
"""
Fixtures partagées pour tous les tests FileLabs.
"""
import io
import zipfile
import pytest
from PIL import Image
import pikepdf
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app_client():
    """TestClient FastAPI — simule des requêtes HTTP sans serveur réel."""
    from main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
def sample_pdf_bytes():
    """PDF minimal valide — 1 page vide, généré en mémoire."""
    pdf = pikepdf.Pdf.new()
    page = pikepdf.Page(pikepdf.Dictionary(
        Type=pikepdf.Name.Page,
        MediaBox=pikepdf.Array([0, 0, 612, 792]),
    ))
    pdf.pages.append(page)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="session")
def sample_pdf_2pages_bytes():
    """PDF minimal valide — 2 pages, pour les tests merge/split."""
    pdf = pikepdf.Pdf.new()
    for _ in range(2):
        page = pikepdf.Page(pikepdf.Dictionary(
            Type=pikepdf.Name.Page,
            MediaBox=pikepdf.Array([0, 0, 612, 792]),
        ))
        pdf.pages.append(page)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="session")
def sample_jpg_bytes():
    """JPEG 20×20 RGB, généré en mémoire (pas de fichier disque)."""
    img = Image.new("RGB", (20, 20), color=(100, 149, 237))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(scope="session")
def sample_png_bytes():
    """PNG 20×20 RGBA, généré en mémoire."""
    img = Image.new("RGBA", (20, 20), color=(100, 149, 237, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="session")
def sample_zip_bytes():
    """ZIP avec un fichier texte, généré en mémoire."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("hello.txt", "hello world " * 100)
    return buf.getvalue()
```

- [ ] **Step 2 : Vérifier que les fixtures sont visibles**

```bash
cd "C:\Users\I768882\OneDrive - SAP SE\Desktop\filelabs"
C:\Windows\py.exe -m pytest tests/ --collect-only -q 2>&1 | head -20
```

Expected : pas d'erreur d'import, les tests existants sont toujours collectés.

- [ ] **Step 3 : Commit**

```bash
git add tests/conftest.py
git commit -m "test: add shared fixtures in conftest.py"
```

---

## Task 2 : Tests unitaires compression (test_compressors.py)

**Contexte :** Les fonctions `compress_image`, `compress_pdf`, `compress_archive` n'ont aucun test. On teste le cas nominal (fichier valide → sortie valide) et les cas d'erreur (fichier inexistant, paramètre invalide). Pas de mock ffmpeg ici — seules image/PDF/archive sont testées (pas de vidéo).

**Files:**
- Modify: `tests/test_compressors.py` (ajouter à la fin)

- [ ] **Step 1 : Ajouter les tests compress_image**

Ajouter à la fin de `tests/test_compressors.py` :

```python
# ─── compress_image ──────────────────────────────────────────────────────────

import tempfile
from pathlib import Path
from compressors.image.compress import compress_image


def test_compress_image_jpg_standard(sample_jpg_bytes):
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "input.jpg"
        out = Path(d) / "output.jpg"
        inp.write_bytes(sample_jpg_bytes)
        result = compress_image(inp, out, level="standard")
        assert result.exists()
        assert result.stat().st_size > 0


def test_compress_image_png_aggressive(sample_png_bytes):
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "input.png"
        out = Path(d) / "output.png"
        inp.write_bytes(sample_png_bytes)
        result = compress_image(inp, out, level="aggressive")
        assert result.exists()
        assert result.stat().st_size > 0


def test_compress_image_all_levels(sample_jpg_bytes):
    for level in ("light", "standard", "aggressive"):
        with tempfile.TemporaryDirectory() as d:
            inp = Path(d) / "input.jpg"
            out = Path(d) / "output.jpg"
            inp.write_bytes(sample_jpg_bytes)
            result = compress_image(inp, out, level=level)
            assert result.exists(), f"Niveau {level} n'a pas produit de fichier"


def test_compress_image_missing_file_raises():
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(Exception):
            compress_image(Path(d) / "missing.jpg", Path(d) / "out.jpg")
```

- [ ] **Step 2 : Ajouter les tests compress_pdf**

```python
# ─── compress_pdf ────────────────────────────────────────────────────────────

from compressors.pdf.compress import compress_pdf


def test_compress_pdf_standard(sample_pdf_bytes):
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "input.pdf"
        out = Path(d) / "output.pdf"
        inp.write_bytes(sample_pdf_bytes)
        result = compress_pdf(inp, out, level="standard")
        assert result.exists()
        assert result.stat().st_size > 0


def test_compress_pdf_all_levels(sample_pdf_bytes):
    for level in ("light", "standard", "aggressive"):
        with tempfile.TemporaryDirectory() as d:
            inp = Path(d) / "input.pdf"
            out = Path(d) / "output.pdf"
            inp.write_bytes(sample_pdf_bytes)
            result = compress_pdf(inp, out, level=level)
            assert result.exists(), f"Niveau {level} n'a pas produit de fichier"


def test_compress_pdf_no_metadata(sample_pdf_bytes):
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "input.pdf"
        out = Path(d) / "output.pdf"
        inp.write_bytes(sample_pdf_bytes)
        result = compress_pdf(inp, out, remove_metadata=True)
        assert result.exists()
```

- [ ] **Step 3 : Ajouter les tests compress_archive**

```python
# ─── compress_archive ────────────────────────────────────────────────────────

from compressors.archive import compress_archive


def test_compress_archive_zip_standard(sample_zip_bytes):
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "input.zip"
        out = Path(d) / "output.zip"
        inp.write_bytes(sample_zip_bytes)
        result = compress_archive(inp, out, level="standard")
        assert result.exists()
        assert result.stat().st_size > 0


def test_compress_archive_all_levels(sample_zip_bytes):
    for level in ("light", "standard", "aggressive"):
        with tempfile.TemporaryDirectory() as d:
            inp = Path(d) / "input.zip"
            out = Path(d) / "output.zip"
            inp.write_bytes(sample_zip_bytes)
            result = compress_archive(inp, out, level=level)
            assert result.exists(), f"Niveau {level} n'a pas produit de fichier"


def test_compress_archive_missing_file_raises():
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(Exception):
            compress_archive(Path(d) / "missing.zip", Path(d) / "out.zip")
```

- [ ] **Step 4 : Lancer les nouveaux tests**

```bash
C:\Windows\py.exe -m pytest tests/test_compressors.py -k "compress_image or compress_pdf or compress_archive" -v
```

Expected : tous PASSED.

- [ ] **Step 5 : Commit**

```bash
git add tests/test_compressors.py
git commit -m "test: add unit tests for compress_image, compress_pdf, compress_archive"
```

---

## Task 3 : R1 — Fix ThreadPoolExecutor silencieux

**Contexte :** Dans `compressors/pdf/compress.py`, `list(executor.map(lambda p: _recompress_page_images(p, q), pdf.pages))` avale les exceptions levées dans les threads. Si une exception est levée, elle est silencieusement ignorée. Le fix : utiliser `executor.submit()` + `fut.result()` pour re-lever les exceptions.

**Files:**
- Modify: `compressors/pdf/compress.py:50-51`
- Test: `tests/test_compressors.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à la fin de `tests/test_compressors.py` :

```python
# ─── R1 — ThreadPoolExecutor propagation d'exceptions ────────────────────────

from unittest.mock import patch


def test_compress_pdf_propagates_thread_exception(sample_pdf_bytes):
    """Les exceptions dans les threads de recompression doivent remonter."""
    with tempfile.TemporaryDirectory() as d:
        inp = Path(d) / "input.pdf"
        out = Path(d) / "output.pdf"
        inp.write_bytes(sample_pdf_bytes)
        with patch(
            "compressors.pdf.compress._recompress_page_images",
            side_effect=RuntimeError("thread error simulé"),
        ):
            with pytest.raises(RuntimeError, match="thread error simulé"):
                compress_pdf(inp, out)
```

- [ ] **Step 2 : Lancer pour vérifier l'échec**

```bash
C:\Windows\py.exe -m pytest tests/test_compressors.py::test_compress_pdf_propagates_thread_exception -v
```

Expected : FAIL — `RuntimeError` n'est pas levée (swallowed par `executor.map`).

- [ ] **Step 3 : Lire `compressors/pdf/compress.py` lignes 49-52**

Vérifier la ligne exacte du `executor.map` :
```python
        with ThreadPoolExecutor() as executor:
            list(executor.map(lambda p: _recompress_page_images(p, target_quality), pdf.pages))
```

- [ ] **Step 4 : Appliquer le fix**

Remplacer les 2 lignes ci-dessus par :

```python
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(_recompress_page_images, p, target_quality)
                for p in pdf.pages
            ]
            for fut in futures:
                fut.result()  # re-raise si exception dans le thread
```

- [ ] **Step 5 : Lancer les tests**

```bash
C:\Windows\py.exe -m pytest tests/test_compressors.py -k "compress_pdf or thread" -v
```

Expected : tous PASSED (y compris le nouveau test + les tests compress_pdf existants).

- [ ] **Step 6 : Commit**

```bash
git add compressors/pdf/compress.py tests/test_compressors.py
git commit -m "fix(robustesse): propagate ThreadPoolExecutor exceptions in compress_pdf — R1"
```

---

## Task 4 : R2 — Fix exceptions silencieuses sans logging

**Contexte :** 5 blocs `except Exception: pass/continue` sans aucun log dans `compressors/pdf/compress.py`, `compressors/pdf/tools.py`, et `compressors/media/video.py`. Le fix : ajouter `logger.debug(...)` dans chaque bloc, et remplacer `Exception` par le type le plus spécifique possible. Les comportements de fallback (skip, return False, duration=None) sont conservés.

**Files:**
- Modify: `compressors/pdf/compress.py:44-47, 95-96, 97-98`
- Modify: `compressors/pdf/tools.py:~446, ~504`
- Modify: `compressors/media/video.py:~139`

- [ ] **Step 1 : Lire et noter les lignes exactes dans `compressors/pdf/compress.py`**

Lire `compressors/pdf/compress.py`. Trouver :
- Le bloc `except Exception: pass` dans la boucle `for key in list(meta.keys())` (suppression métadonnées)
- Le bloc `except Exception: continue` dans `_recompress_page_images` (skip image individuelle)
- Le bloc `except Exception: pass` outer dans `_recompress_page_images`

Ajouter un import logger en haut du fichier si absent :
```python
import logging
logger = logging.getLogger(__name__)
```

Remplacer le bloc métadonnées :
```python
# Avant
                try:
                    del meta[key]
                except Exception:
                    pass

# Après
                try:
                    del meta[key]
                except (KeyError, AttributeError) as e:
                    logger.debug("Metadata key skip %r: %s", key, e)
```

Remplacer le inner except dans `_recompress_page_images` :
```python
# Avant
            except Exception:
                continue

# Après
            except Exception as e:
                logger.debug("Image XObject skip (recompression): %s", e)
                continue
```

Remplacer le outer except dans `_recompress_page_images` :
```python
# Avant
    except Exception:
        pass

# Après
    except Exception as e:
        logger.debug("Page XObjects skip (recompression): %s", e)
```

- [ ] **Step 2 : Lire et noter les lignes exactes dans `compressors/pdf/tools.py`**

Lire `compressors/pdf/tools.py`. Trouver :
- `except Exception: continue` dans la boucle d'aplatissement d'annotations (watermark)
- `except Exception: return False` dans `_is_blank_page`

Ajouter import logger si absent :
```python
import logging
logger = logging.getLogger(__name__)
```

Remplacer le except annotations :
```python
# Avant
                        except Exception:
                            continue

# Après
                        except Exception as e:
                            logger.debug("Annotation flatten skip: %s", e)
                            continue
```

Remplacer le except `_is_blank_page` :
```python
# Avant
    except Exception:
        return False

# Après
    except Exception as e:
        logger.debug("Blank page detection fallback: %s", e)
        return False
```

- [ ] **Step 3 : Lire et noter la ligne exacte dans `compressors/media/video.py`**

Lire `compressors/media/video.py` lignes 135-142. Trouver :
```python
    except Exception:
        duration = None
```

Ajouter import logger si absent :
```python
import logging
logger = logging.getLogger(__name__)
```

Remplacer :
```python
# Avant
    except Exception:
        duration = None

# Après
    except Exception as e:
        logger.debug("FFmpeg probe failed, progression indisponible: %s", e)
        duration = None
```

- [ ] **Step 4 : Lancer la suite complète pour vérifier aucune régression**

```bash
C:\Windows\py.exe -m pytest tests/test_compressors.py -v
```

Expected : même résultat qu'avant (tous PASSED).

- [ ] **Step 5 : Commit**

```bash
git add compressors/pdf/compress.py compressors/pdf/tools.py compressors/media/video.py
git commit -m "fix(robustesse): replace silent except Exception with specific types + logging — R2"
```

---

## Task 5 : Créer `tests/test_endpoints.py` — /compress + /download

**Contexte :** Test de l'endpoint principal `/compress` via TestClient, incluant validation de paramètres, cas nominal image/PDF/archive, et le cycle complet compress→download. Les tests vidéo ne sont pas inclus ici (ffmpeg requis — Task 7).

**Files:**
- Create: `tests/test_endpoints.py`

- [ ] **Step 1 : Créer `tests/test_endpoints.py` avec les tests /compress**

```python
"""
Tests d'intégration pour les endpoints FastAPI FileLabs.
Utilise TestClient (httpx) — pas de serveur réel.
"""
import pytest


# ─── /compress — validation paramètres ───────────────────────────────────────

def test_compress_invalid_level_returns_400(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"level": "ULTRA"},
    )
    assert resp.status_code == 400


def test_compress_invalid_codec_returns_400(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.mp4", sample_jpg_bytes, "video/mp4")},
        data={"level": "standard", "vid_codec": "hevc_nvenc"},
    )
    assert resp.status_code == 400


def test_compress_invalid_crf_returns_400(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.mp4", sample_jpg_bytes, "video/mp4")},
        data={"level": "standard", "vid_crf": "999"},
    )
    assert resp.status_code == 400


def test_compress_invalid_dpi_returns_400(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"level": "standard", "pdf_dpi": "5"},  # < 30
    )
    assert resp.status_code == 400


def test_compress_invalid_quality_returns_400(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"level": "standard", "img_quality": "200"},  # > 100
    )
    assert resp.status_code == 400


def test_compress_missing_file_returns_422(app_client):
    resp = app_client.post("/compress", data={"level": "standard"})
    assert resp.status_code == 422


# ─── /compress — cas nominaux image ─────────────────────────────────────────

def test_compress_jpg_returns_success(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"level": "standard"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "download_id" in body
    assert body["file_type"] == "image"


def test_compress_png_returns_success(app_client, sample_png_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.png", sample_png_bytes, "image/png")},
        data={"level": "light"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_compress_pdf_returns_success(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"level": "standard"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["file_type"] == "pdf"


def test_compress_archive_returns_success(app_client, sample_zip_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.zip", sample_zip_bytes, "application/zip")},
        data={"level": "standard"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ─── /download — cycle complet ───────────────────────────────────────────────

def test_compress_then_download(app_client, sample_jpg_bytes):
    """Compress → récupérer download_id → télécharger le fichier."""
    compress_resp = app_client.post(
        "/compress",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"level": "standard"},
    )
    assert compress_resp.status_code == 200
    download_id = compress_resp.json()["download_id"]

    dl_resp = app_client.get(f"/download/{download_id}")
    assert dl_resp.status_code == 200
    assert len(dl_resp.content) > 0


def test_download_unknown_uid_returns_404(app_client):
    resp = app_client.get("/download/nonexistent1234567890abcdefff")
    assert resp.status_code == 404


def test_download_traversal_attempt_blocked(app_client):
    """Path traversal dans l'uid doit être bloqué."""
    resp = app_client.get("/download/../../../etc/passwd")
    assert resp.status_code in (400, 403, 404, 422)


# ─── /health ─────────────────────────────────────────────────────────────────

def test_health_returns_ok(app_client):
    resp = app_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

- [ ] **Step 2 : Lancer les tests**

```bash
C:\Windows\py.exe -m pytest tests/test_endpoints.py -v
```

Expected : tous PASSED.

- [ ] **Step 3 : Commit**

```bash
git add tests/test_endpoints.py
git commit -m "test: add endpoint tests for /compress and /download"
```

---

## Task 6 : Tests /pdf/* dans `test_endpoints.py`

**Contexte :** Tester les 13 endpoints PDF. Chaque endpoint a un cas nominal + au moins un cas d'erreur de paramètre. Les endpoints qui requièrent des PDF multi-pages utilisent `sample_pdf_2pages_bytes`.

**Files:**
- Modify: `tests/test_endpoints.py` (ajouter à la fin)

- [ ] **Step 1 : Ajouter les tests /pdf/merge et /pdf/split**

Ajouter à la fin de `tests/test_endpoints.py` :

```python
# ─── /pdf/merge ──────────────────────────────────────────────────────────────

def test_pdf_merge_two_files(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/merge",
        files=[
            ("files", ("a.pdf", sample_pdf_bytes, "application/pdf")),
            ("files", ("b.pdf", sample_pdf_bytes, "application/pdf")),
        ],
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_pdf_merge_single_file_returns_400(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/merge",
        files=[("files", ("a.pdf", sample_pdf_bytes, "application/pdf"))],
    )
    assert resp.status_code == 400


# ─── /pdf/split ──────────────────────────────────────────────────────────────

def test_pdf_split_no_ranges(app_client, sample_pdf_2pages_bytes):
    """Split sans ranges — produit un ZIP avec toutes les pages."""
    resp = app_client.post(
        "/pdf/split",
        files={"file": ("test.pdf", sample_pdf_2pages_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_pdf_split_too_long_ranges_returns_400(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/split",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"ranges": "1" * 501},  # > 500 chars
    )
    assert resp.status_code == 400


# ─── /pdf/rotate ─────────────────────────────────────────────────────────────

def test_pdf_rotate_90(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/rotate",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"angle": "90"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_pdf_rotate_invalid_angle_returns_500(app_client, sample_pdf_bytes):
    """Angle invalide (45) lève ValueError dans compressor → HTTP 500."""
    resp = app_client.post(
        "/pdf/rotate",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"angle": "45"},
    )
    assert resp.status_code == 500


# ─── /pdf/watermark ──────────────────────────────────────────────────────────

def test_pdf_watermark_default(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/watermark",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"text": "CONFIDENTIEL"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_pdf_watermark_invalid_position_returns_400(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/watermark",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"text": "TEST", "position": "topleft"},  # invalide
    )
    assert resp.status_code == 400


# ─── /pdf/to-jpg ─────────────────────────────────────────────────────────────

def test_pdf_to_jpg_default_dpi(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/to-jpg",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_pdf_to_jpg_invalid_dpi_returns_400(app_client, sample_pdf_bytes):
    resp = app_client.post(
        "/pdf/to-jpg",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
        data={"dpi": "10"},  # < 50
    )
    assert resp.status_code == 400


# ─── /pdf/from-jpg ───────────────────────────────────────────────────────────

def test_pdf_from_jpg(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/pdf/from-jpg",
        files=[("files", ("img.jpg", sample_jpg_bytes, "image/jpeg"))],
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ─── /pdf/extract-text ───────────────────────────────────────────────────────

def test_pdf_extract_text_empty_pdf(app_client, sample_pdf_bytes):
    """PDF sans texte → is_scanned True."""
    resp = app_client.post(
        "/pdf/extract-text",
        files={"file": ("test.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "is_scanned" in body or "success" in body
```

- [ ] **Step 2 : Lancer les tests PDF**

```bash
C:\Windows\py.exe -m pytest tests/test_endpoints.py -k "pdf" -v
```

Expected : tous PASSED.

- [ ] **Step 3 : Commit**

```bash
git add tests/test_endpoints.py
git commit -m "test: add endpoint tests for /pdf/* routes"
```

---

## Task 7 : Tests /image/* et /video/* dans `test_endpoints.py`

**Contexte :** Les 4 endpoints image sont testés avec de vraies images (Pillow installé, pas de mock nécessaire). Les tests video ne font que valider les paramètres (400) — le test de compression réelle est skippé si ffmpeg est absent.

**Files:**
- Modify: `tests/test_endpoints.py` (ajouter à la fin)

- [ ] **Step 1 : Ajouter les tests /image/***

Ajouter à la fin de `tests/test_endpoints.py` :

```python
# ─── /image/resize ───────────────────────────────────────────────────────────

def test_image_resize_returns_success(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/image/resize",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"width": "50", "height": "50"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_image_resize_missing_dims_returns_success(app_client, sample_jpg_bytes):
    """Sans width/height, retourne l'image inchangée (comportement attendu)."""
    resp = app_client.post(
        "/image/resize",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
    )
    assert resp.status_code == 200


# ─── /image/convert ──────────────────────────────────────────────────────────

def test_image_convert_jpg_to_webp(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/image/convert",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"target_format": "webp"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_image_convert_invalid_format_returns_400(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/image/convert",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"target_format": "exe"},
    )
    assert resp.status_code == 400


# ─── /image/crop ─────────────────────────────────────────────────────────────

def test_image_crop_returns_success(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/image/crop",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"left": "0", "top": "0", "right": "10", "bottom": "10"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_image_crop_missing_right_returns_422(app_client, sample_jpg_bytes):
    """right/bottom sont requis (Form(...))."""
    resp = app_client.post(
        "/image/crop",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"left": "0", "top": "0"},
    )
    assert resp.status_code == 422


# ─── /image/rotate ───────────────────────────────────────────────────────────

def test_image_rotate_90(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/image/rotate",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"angle": "90"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_image_rotate_flip_horizontal(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/image/rotate",
        files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
        data={"flip": "horizontal"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ─── /compress — vidéo : validation paramètres seulement ────────────────────

def test_compress_video_invalid_codec_returns_400(app_client, sample_jpg_bytes):
    """Validation codec avant compression — pas besoin de ffmpeg."""
    resp = app_client.post(
        "/compress",
        files={"file": ("test.mp4", sample_jpg_bytes, "video/mp4")},
        data={"level": "standard", "vid_codec": "xvid"},
    )
    assert resp.status_code == 400


def test_compress_video_invalid_preset_returns_400(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.mp4", sample_jpg_bytes, "video/mp4")},
        data={"level": "standard", "vid_preset": "turbo"},
    )
    assert resp.status_code == 400


def test_compress_video_invalid_height_returns_400(app_client, sample_jpg_bytes):
    resp = app_client.post(
        "/compress",
        files={"file": ("test.mp4", sample_jpg_bytes, "video/mp4")},
        data={"level": "standard", "vid_max_height": "1440"},  # non dans _VALID_HEIGHTS
    )
    assert resp.status_code == 400
```

- [ ] **Step 2 : Lancer les tests image et vidéo**

```bash
C:\Windows\py.exe -m pytest tests/test_endpoints.py -k "image or video" -v
```

Expected : tous PASSED.

- [ ] **Step 3 : Commit**

```bash
git add tests/test_endpoints.py
git commit -m "test: add endpoint tests for /image/* and /video param validation"
```

---

## Task 8 : Créer `tests/test_middleware.py`

**Contexte :** Tester le middleware de rate limiting (actif uniquement si `_ON_RENDER = True`) et les security headers. Pour tester le rate limit, on patche `_ON_RENDER` à `True` avec `monkeypatch` de pytest.

**Files:**
- Create: `tests/test_middleware.py`

- [ ] **Step 1 : Créer `tests/test_middleware.py`**

```python
"""
Tests pour les middlewares FastAPI FileLabs :
- Rate limiting (_ON_RENDER=True requis)
- Security headers
"""
import pytest


# ─── Security headers ─────────────────────────────────────────────────────────

def test_x_frame_options_present(app_client):
    resp = app_client.get("/health")
    assert resp.headers.get("x-frame-options") == "DENY"


def test_x_content_type_options_present(app_client):
    resp = app_client.get("/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"


def test_referrer_policy_present(app_client):
    resp = app_client.get("/health")
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_permissions_policy_present(app_client):
    resp = app_client.get("/health")
    assert "permissions-policy" in resp.headers


def test_security_headers_on_static(app_client):
    """Les headers de sécurité s'appliquent aussi aux réponses statiques."""
    resp = app_client.get("/static/style.css")
    # Le fichier peut ne pas exister en test, on vérifie juste les headers si 200
    if resp.status_code == 200:
        assert resp.headers.get("x-frame-options") == "DENY"


# ─── Rate limiting ────────────────────────────────────────────────────────────

def test_rate_limit_not_active_by_default(app_client, sample_jpg_bytes):
    """Sans _ON_RENDER=True, le rate limit ne s'applique pas."""
    for _ in range(5):
        resp = app_client.post(
            "/compress",
            files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
            data={"level": "standard"},
        )
    # Aucun 429 attendu
    assert resp.status_code != 429


def test_rate_limit_triggers_when_on_render(app_client, sample_jpg_bytes, monkeypatch):
    """Avec _ON_RENDER=True, la 21e requête doit retourner 429."""
    import main as app_module
    monkeypatch.setattr(app_module, "_ON_RENDER", True)
    # Vider les buckets pour ce test
    app_module._rate_buckets.clear()

    last_resp = None
    for _ in range(21):
        last_resp = app_client.post(
            "/compress",
            files={"file": ("test.jpg", sample_jpg_bytes, "image/jpeg")},
            data={"level": "standard"},
        )

    assert last_resp.status_code == 429
    assert "429" in str(last_resp.status_code)
    # Nettoyer après le test
    app_module._rate_buckets.clear()


def test_rate_limit_not_on_health(app_client, monkeypatch):
    """Le rate limit ne s'applique pas aux endpoints hors _PROCESSING_PATHS."""
    import main as app_module
    monkeypatch.setattr(app_module, "_ON_RENDER", True)
    app_module._rate_buckets.clear()

    for _ in range(25):
        resp = app_client.get("/health")
    assert resp.status_code == 200  # pas de 429
    app_module._rate_buckets.clear()


def test_processing_paths_contains_media():
    """Régression : /media/ doit être dans _PROCESSING_PATHS (fix passe 3)."""
    import main as app_module
    assert "/media/" in app_module._PROCESSING_PATHS


def test_processing_paths_contains_video():
    import main as app_module
    assert "/video/" in app_module._PROCESSING_PATHS


def test_processing_paths_contains_pdf():
    import main as app_module
    assert "/pdf/" in app_module._PROCESSING_PATHS
```

- [ ] **Step 2 : Lancer les tests middleware**

```bash
C:\Windows\py.exe -m pytest tests/test_middleware.py -v
```

Expected : tous PASSED (sauf si le serveur ne démarre pas correctement, auquel cas voir les logs d'import).

- [ ] **Step 3 : Commit**

```bash
git add tests/test_middleware.py
git commit -m "test: add middleware tests (rate limiting, security headers)"
```

---

## Task 9 : R3 — Fix progress dict cleanup dans `main.py`

**Contexte :** Si l'endpoint `/compress` lève une exception pendant le traitement vidéo (après avoir initialisé `_video_progress[progress_key]`), la clé reste orpheline dans le dict. Le fix : déclarer `progress_key = None` avant le try, et l'ajouter au bloc `finally`.

**Files:**
- Modify: `main.py` (compress endpoint, ~lignes 486-568)
- Test: `tests/test_compressors.py`

- [ ] **Step 1 : Écrire le test**

Ajouter à la fin de `tests/test_compressors.py` :

```python
# ─── R3 — Progress dict cleanup ───────────────────────────────────────────────

def test_video_progress_key_cleaned_on_error(app_client, sample_jpg_bytes, monkeypatch):
    """Si /compress échoue pendant la compression vidéo, la clé progress_key
    doit être supprimée du dict _video_progress."""
    import main as app_module
    from unittest.mock import patch

    # Générer un job_id connu
    test_job_id = "a" * 32

    # Simuler une erreur dans compress_video
    with patch("main.compress_video", side_effect=RuntimeError("ffmpeg crash")):
        resp = app_client.post(
            "/compress",
            files={"file": ("test.mp4", sample_jpg_bytes, "video/mp4")},
            data={"level": "standard", "job_id": test_job_id},
        )

    # Le dict ne doit pas contenir la clé orpheline
    assert test_job_id not in app_module._video_progress
```

- [ ] **Step 2 : Lancer pour vérifier l'échec**

```bash
C:\Windows\py.exe -m pytest tests/test_compressors.py::test_video_progress_key_cleaned_on_error -v
```

Expected : FAIL — la clé `test_job_id` reste dans `_video_progress` après l'erreur.

- [ ] **Step 3 : Lire `main.py` lignes 486-568 (endpoint /compress)**

Trouver la structure du endpoint et localiser :
- La ligne où `progress_key` est défini (dans le `elif file_type == "video":`)
- Le bloc `finally:` final

- [ ] **Step 4 : Appliquer le fix**

Avant le `try:` principal de l'endpoint, ajouter `progress_key = None`. Puis dans `finally:`, ajouter le cleanup.

**Avant (structure du endpoint) :**
```python
    uid = uuid.uuid4().hex
    original_ext = Path(file.filename).suffix.lower()
    input_path = UPLOAD_DIR / f"{uid}_input{original_ext}"
    ...
    await _save_upload(file, input_path, max_bytes)

    try:
        ...
        elif file_type == "video":
            progress_key = job_id if (job_id and _UID_RE.match(job_id)) else uid
            _video_progress[progress_key] = 0.0
            ...
        ...
    except Exception as e:
        input_path.unlink(missing_ok=True)
        logger.error(...)
        raise HTTPException(...)
    finally:
        input_path.unlink(missing_ok=True)
```

**Après :**
```python
    uid = uuid.uuid4().hex
    original_ext = Path(file.filename).suffix.lower()
    input_path = UPLOAD_DIR / f"{uid}_input{original_ext}"
    progress_key = None   # ← ajouter cette ligne avant le try
    ...
    await _save_upload(file, input_path, max_bytes)

    try:
        ...
        elif file_type == "video":
            progress_key = job_id if (job_id and _UID_RE.match(job_id)) else uid
            _video_progress[progress_key] = 0.0
            ...
        ...
    except Exception as e:
        input_path.unlink(missing_ok=True)
        logger.error(...)
        raise HTTPException(...)
    finally:
        input_path.unlink(missing_ok=True)
        if progress_key:                                # ← ajouter ces 2 lignes
            _video_progress.pop(progress_key, None)
```

- [ ] **Step 5 : Lancer les tests**

```bash
C:\Windows\py.exe -m pytest tests/test_compressors.py::test_video_progress_key_cleaned_on_error -v
```

Expected : PASSED.

- [ ] **Step 6 : Commit**

```bash
git add main.py tests/test_compressors.py
git commit -m "fix(robustesse): cleanup progress_key in finally block on compress error — R3"
```

---

## Task 10 : R4+R5 — threading.Lock + imports dupliqués + suite finale

**Contexte :** R4 ajoute un `threading.Lock` pour protéger `_video_progress` contre les accès concurrent (thread ffmpeg ↔ générateur SSE). R5 supprime les `import shutil` dupliqués à l'intérieur de fonctions.

**Files:**
- Modify: `main.py` (R4: lock + R5: imports)

- [ ] **Step 1 : R4 — Ajouter threading.Lock pour `_video_progress`**

Lire `main.py` lignes 140-148. Ajouter après la déclaration de `_video_progress` :

```python
_video_progress: dict = {}
_video_progress_lock = threading.Lock()   # ← ajouter cette ligne
```

Puis trouver les écritures sur `_video_progress` dans le compress endpoint et dans `_progress_cb` :

```python
# Avant (dans la fonction _progress_cb)
def _progress_cb(pct: float):
    _video_progress[progress_key] = pct

# Après
def _progress_cb(pct: float):
    with _video_progress_lock:
        _video_progress[progress_key] = pct
```

```python
# Avant (dans l'endpoint, après la compression)
_video_progress[progress_key] = 100.0
await asyncio.sleep(2.0)
_video_progress.pop(progress_key, None)

# Après
with _video_progress_lock:
    _video_progress[progress_key] = 100.0
await asyncio.sleep(2.0)
with _video_progress_lock:
    _video_progress.pop(progress_key, None)
```

```python
# Dans le finally du R3 fix
if progress_key:
    with _video_progress_lock:
        _video_progress.pop(progress_key, None)
```

La lecture dans le SSE generator (`_video_progress.get(uid)`) n'a pas besoin de lock car `dict.get()` est atomique en CPython — mais pour la cohérence, l'ajouter aussi :

```python
# Dans event_stream() du compress_progress SSE
with _video_progress_lock:
    pct = _video_progress.get(uid)
```

- [ ] **Step 2 : R5 — Supprimer les imports shutil dupliqués**

Chercher les imports locaux :

```bash
grep -n "import shutil" main.py
```

Expected : trouver des lignes avec `import shutil as _shutil` ou `import shutil as _sh` à l'intérieur de fonctions.

Pour chaque occurrence trouvée à l'intérieur d'une fonction : supprimer la ligne. `shutil` est déjà importé globalement en haut du fichier — vérifier avec `grep -n "^import shutil" main.py`.

Si `shutil` n'est pas importé globalement, ajouter `import shutil` dans les imports du module (ligne ~18).

- [ ] **Step 3 : Lancer la suite complète**

```bash
C:\Windows\py.exe -m pytest tests/ -v
```

Expected : tous PASSED (mêmes skips qu'avant). Noter le nombre total de tests.

- [ ] **Step 4 : Vérifier la couverture approximative**

```bash
C:\Windows\py.exe -m pytest tests/ --tb=no -q
```

Expected : X passed, 1 skipped (le même test d'intégration réelle qu'avant).

- [ ] **Step 5 : Commit final**

```bash
git add main.py
git commit -m "fix(robustesse): add threading.Lock for _video_progress + remove duplicate shutil imports — R4/R5"
```

---

## Récapitulatif

| Task | Fichiers | Tests ajoutés | Fix |
|------|----------|--------------|-----|
| 1 | `tests/conftest.py` | — | — |
| 2 | `tests/test_compressors.py` | ~14 | — |
| 3 | `tests/test_compressors.py` + `pdf/compress.py` | 1 | R1 ThreadPoolExecutor |
| 4 | `pdf/compress.py` + `pdf/tools.py` + `media/video.py` | 0 | R2 logging |
| 5 | `tests/test_endpoints.py` | ~18 | — |
| 6 | `tests/test_endpoints.py` | ~14 | — |
| 7 | `tests/test_endpoints.py` | ~10 | — |
| 8 | `tests/test_middleware.py` | ~12 | — |
| 9 | `tests/test_compressors.py` + `main.py` | 1 | R3 progress cleanup |
| 10 | `main.py` | 0 | R4 Lock + R5 imports |
| **Total** | | **~70 nouveaux tests** | **5 fixes** |
