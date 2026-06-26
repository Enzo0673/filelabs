# Robustesse & Tests — FileLabs (Passe 1)

**Date :** 2026-06-26
**Périmètre :** Couverture de tests exhaustive (~120 tests) + 5 fixes robustesse identifiés lors de l'audit de code
**Approche :** Tests d'abord — chaque test qui échoue révèle un bug à corriger

---

## Contexte

L'audit de code a identifié deux catégories de problèmes :

- **Robustesse :** erreurs silencieuses (`except Exception: pass`), état global sans cleanup (TTL manquant sur `_video_progress`, `_download_progress`), race condition sur les dicts partagés entre threads, imports dupliqués.
- **Couverture de tests :** ~30% des chemins critiques couverts. Les fonctions de compression (`compress_image`, `compress_video`, `compress_pdf`, `compress_archive`), les endpoints FastAPI, et le middleware sont sans tests.

---

## Architecture des tests

### Structure cible

```
tests/
  conftest.py              — fixtures partagées (TestClient, fichiers samples en mémoire)
  test_compressors.py      — existant (56 tests), étendu avec tests unitaires compresseurs
  test_endpoints.py        — nouveau : tous les endpoints FastAPI
  test_middleware.py       — nouveau : rate limiting, security headers
```

### `conftest.py` — Fixtures

| Fixture | Type | Description |
|---------|------|-------------|
| `client` | `TestClient` | Instance FastAPI pour les tests d'intégration |
| `sample_pdf` | `bytes` | PDF minimal valide (1 page, généré en mémoire) |
| `sample_image_jpg` | `bytes` | JPEG 10×10px RGB |
| `sample_image_png` | `bytes` | PNG 10×10px RGBA |
| `sample_video_mp4` | `bytes` | MP4 minimal (header ftyp uniquement, ~100 bytes) |
| `sample_zip` | `bytes` | ZIP minimal avec un fichier texte |

Les fichiers samples sont générés en mémoire (Pillow pour images, pikepdf pour PDF, zipfile pour archives). Aucune dépendance sur des fichiers disque.

### `test_compressors.py` — Extensions

Ajouter ~40 tests unitaires pour les fonctions de compression et d'édition :

**Compression :**
- `compress_image` : formats JPEG/PNG/WebP, niveaux light/standard/aggressive, fichier manquant → ValueError
- `compress_pdf` : réduction de taille, PDF corrompu → exception catchée
- `compress_archive` : ZIP/TAR, protection zip bomb (déjà partiellement testée)
- `compress_video` : mocké (ffmpeg), vérification des paramètres passés

**PDF tools :**
- `merge_pdfs` : 2 PDFs → 1, liste vide → ValueError
- `split_pdf` : ranges valides, hors bornes → ValueError
- `rotate_pdf` : angles valides (90/180/270), invalide → ValueError
- `watermark_pdf` : texte normal, texte avec caractères spéciaux (déjà testé)
- `extract_text` : PDF avec texte, PDF sans texte → retourne ""

**Image tools :**
- `resize_image` : dimensions valides, ratio maintenu
- `convert_image` : JPEG→PNG, PNG→WebP
- `crop_image` : coordonnées valides, hors bornes → ValueError
- `rotate_image` : 90/180/270/flip

**Video tools :**
- Tous mockés ffmpeg : `trim_video`, `resize_video`, `merge_videos`, `add_text_video`
- Vérification des arguments ffmpeg-python passés (codec, CRF, etc.)

### `test_endpoints.py` — Endpoints FastAPI

~60 tests via `TestClient`. Structure par groupe d'endpoints :

**Compress générique (`/compress`) :**
- Cas nominal image (retourne download_id)
- Cas nominal PDF
- Fichier trop grand → 413
- Extension invalide → 400
- Niveau invalide → 400

**PDF endpoints (13 endpoints) :**
- Chaque endpoint : cas nominal + au moins 1 cas d'erreur paramètre
- `/pdf/merge` : 2 fichiers → 200 ; 1 seul fichier → 400
- `/pdf/watermark` : position invalide → 400 ; couleur invalide → 400
- `/pdf/protect` : mot de passe vide → 400 ; mot de passe valide → 200

**Image endpoints (4 endpoints) :**
- `/image/resize` : dimensions valides → 200 ; négatif → 400
- `/image/convert` : format cible valide → 200 ; format inconnu → 400

**Video endpoints (4 endpoints) :**
- Tous mockés ffmpeg via `unittest.mock.patch`
- Vérification de la réponse JSON (download_id présent)

**Download :**
- `/download/{uid}` : uid valide → fichier ; uid inconnu → 404 ; traversal tenté → 400

**Downloader (image + video) :**
- `/media/info` : URL invalide → 400 ; IP privée → 400 (SSRF)
- `/video/download/info` : URL invalide → 400

### `test_middleware.py` — Middleware

~15 tests :

**Rate limiting :**
- Requête normale → 200
- N+1 requêtes sur path `/compress` → 429 (mock `_ON_RENDER = True`)
- Path `/media/` déclenche bien le rate limit (fix F2 de la passe 3)
- Path hors `_PROCESSING_PATHS` → pas de rate limit

**Security headers :**
- Chaque header présent sur réponse HTML : `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, `Content-Security-Policy`
- CSP contient les valeurs attendues

---

## Fixes robustesse

### R1 — ThreadPoolExecutor silencieux (`pdf/compress.py`)

**Problème :** `list(executor.map(fn, pages))` avale les exceptions des threads.

**Fix :**
```python
# Avant
with ThreadPoolExecutor() as executor:
    list(executor.map(lambda p: _recompress_page_images(p, target_quality), pdf.pages))

# Après
with ThreadPoolExecutor() as executor:
    futures = [executor.submit(_recompress_page_images, p, target_quality) for p in pdf.pages]
    for fut in futures:
        fut.result()  # re-raise si exception dans le thread
```

**Test associé :** `test_compress_pdf_propagates_thread_exception` — mock `_recompress_page_images` pour lever une exception, vérifier qu'elle remonte.

### R2 — `except Exception: pass/continue` silencieux

**Fichiers concernés :**
- `compressors/pdf/tools.py` ligne ~446 : annotation pikepdf non supportée → `continue` (acceptable, mais doit être loggé)
- `compressors/pdf/tools.py` ligne ~504 : détection page blanche → `return False` (acceptable)
- `compressors/media/video.py` ligne ~139 : probe FFmpeg → `duration = None` (acceptable)

**Fix :** Remplacer `except Exception:` par le type spécifique quand connu, ajouter `logger.debug(...)` dans tous les cas.

```python
# Avant
except Exception:
    continue

# Après
except pikepdf.PdfError as e:
    logger.debug("Annotation non supportée, skip: %s", e)
    continue
```

**Test associé :** Vérifier que les cas normaux fonctionnent toujours (les exceptions spécifiques sont catchées).

### R3 — État global sans TTL (`main.py`)

**Problème :** `_video_progress[uid]` et `_download_progress[uid]` insérés mais pas toujours supprimés si la connexion SSE se ferme avant la fin.

**Fix :** Ajouter `finally:` dans les générateurs SSE pour supprimer la clé :

```python
# Dans video_progress_stream et download_progress_stream
async def event_gen():
    try:
        # ... logique existante
    finally:
        _video_progress.pop(uid, None)
        # ou _download_progress.pop(uid, None)
```

**Test associé :** `test_progress_key_cleaned_up_after_sse_disconnect` — vérifier qu'après fermeture du stream, la clé disparaît du dict.

### R4 — Race condition sur `_video_progress` (`main.py`)

**Problème :** Thread FFmpeg écrit `_video_progress[key] = pct` pendant que le générateur SSE lit `_video_progress.get(key)`. Pas de synchronisation.

**Fix :** Ajouter un `threading.Lock` au niveau module :

```python
_video_progress_lock = threading.Lock()

# Écriture (thread FFmpeg)
with _video_progress_lock:
    _video_progress[key] = pct

# Lecture (SSE)
with _video_progress_lock:
    pct = _video_progress.get(uid)
```

**Test associé :** `test_video_progress_thread_safety` — écriture et lecture concurrentes, vérifier pas de KeyError.

### R5 — Imports `shutil` dupliqués (`main.py`)

**Problème :** `shutil` est importé globalement ligne 18, puis réimporté localement dans 2 fonctions (`import shutil as _shutil`, `import shutil as _sh`).

**Fix :** Supprimer les 2 imports locaux, utiliser l'import global directement.

**Test associé :** Aucun test nécessaire — vérifiable par grep.

---

## Ordre d'implémentation

| Task | Contenu | Tests associés |
|------|---------|----------------|
| 1 | `conftest.py` avec toutes les fixtures | — |
| 2 | `test_compressors.py` — compression units | Compresseurs |
| 3 | R1 fix ThreadPoolExecutor | test_compress_pdf propagation |
| 4 | R2 fix except silencieux | Tests compresseurs passent |
| 5 | `test_endpoints.py` — compress + PDF | Endpoints compress/PDF |
| 6 | `test_endpoints.py` — image + video + download | Endpoints image/video |
| 7 | `test_middleware.py` | Rate limit + headers |
| 8 | R3 fix TTL progress dicts | test_progress_cleanup |
| 9 | R4 fix threading.Lock | test_thread_safety |
| 10 | R5 fix imports dupliqués | grep vérification |

---

## Critères de succès

- `pytest tests/ -v` : tous PASSED (même skips qu'avant)
- Couverture ≥ 80% sur `compressors/` et les chemins critiques de `main.py`
- Aucun `except Exception: pass` sans log dans les compresseurs
- `_video_progress` et `_download_progress` : clés supprimées après fermeture SSE
- Imports `shutil` non dupliqués dans `main.py`
