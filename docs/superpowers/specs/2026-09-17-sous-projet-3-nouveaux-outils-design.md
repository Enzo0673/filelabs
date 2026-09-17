# Sous-projet 3 — Nouveaux outils FileLabs

**Date :** 2026-09-17
**Statut :** Approuvé

## Contexte

Ajout de 9 nouveaux outils à FileLabs, groupés en 3 branches indépendantes. Chaque groupe peut être mergé séparément.

---

## Groupe 1 — PDF (`feat/sp3-pdf`)

### Extraire images PDF

- **Endpoint :** `POST /pdf/extract-images`
- **Paramètre :** `mode` = `embedded` (défaut) ou `pages`
- **Mode `embedded` :** extrait les XObjects Image via pikepdf, retourne un ZIP de PNG/JPEG
- **Mode `pages` :** convertit chaque page en JPEG via pdf2image/poppler, retourne un ZIP
- **Implémentation :** `extract_pdf_images(path, mode)` dans `compressors/pdf/tools.py`

### Signature PDF

- **Endpoint :** `POST /pdf/add-signature`
- **Entrées :** fichier PDF + fichier PNG de signature (deux `UploadFile`)
- **Paramètres :** `page` (int, défaut 1), `x`, `y`, `width` (float, en points PDF)
- **Implémentation :** `add_pdf_signature(pdf_path, sig_path, page, x, y, width)` dans `compressors/pdf/tools.py` via pikepdf XObject injection

---

## Groupe 2 — Image (`feat/sp3-image`)

### Filigrane image

- **Endpoint :** `POST /image/watermark`
- **Paramètres :** `text` (str, optionnel) OU `logo` (UploadFile PNG, optionnel), `position` (top-left/top-right/bottom-left/bottom-right/center, défaut bottom-right), `opacity` (0-100, défaut 50)
- **Texte :** Pillow `ImageDraw` + `ImageFont` (fallback font système)
- **Logo :** colle le PNG redimensionné à 20% de la largeur source avec alpha compositing
- **Implémentation :** `watermark_image(path, out, text, logo_path, position, opacity)` dans `compressors/image/filters.py`

### N&B / Sépia

- **Endpoint :** `POST /image/filter`
- **Paramètre :** `filter` = `grayscale` ou `sepia`
- **Grayscale :** `img.convert("L").convert("RGB")`
- **Sépia :** formule Pillow pure (matrice RGB, pas de numpy)
- **Implémentation :** `apply_filter(path, out, filter)` dans `compressors/image/filters.py`

### Agrandir image

- **Endpoint :** `POST /image/upscale`
- **Paramètre :** `scale` = `2x`, `3x` ou `4x`
- **Resampling :** `Image.LANCZOS`
- **Guard :** refuse si résultat > 50 MP (raise `ValueError`)
- **Implémentation :** `upscale_image(path, out, scale)` dans `compressors/image/filters.py`

---

## Groupe 3 — Media & Utils (`feat/sp3-media-utils`)

### Extraire audio

- **Endpoint :** `POST /video/extract-audio`
- **Paramètre :** `format` = `mp3` (défaut) ou `wav`
- **ffmpeg :** `-vn -acodec libmp3lame` (mp3) ou `-acodec pcm_s16le` (wav)
- **Implémentation :** `extract_audio(path, out, format)` dans `compressors/media/video.py`

### Thumbnails vidéo

- **Endpoint :** `POST /video/thumbnails`
- **Paramètre :** `count` (int, 1-10, défaut 5)
- **ffmpeg :** probe durée → interval = durée/count → `-vf fps=1/interval`
- **Retour :** ZIP de JPEG
- **Implémentation :** `extract_thumbnails(path, out_dir, count)` dans `compressors/media/video.py`

### Hasher fichier

- **Endpoint :** `POST /utils/hash`
- **Paramètre :** `algorithms` (liste, parmi `md5`/`sha256`/`sha512`, défaut `["md5","sha256"]`)
- **Retour :** JSON direct `{"md5": "...", "sha256": "..."}` (pas de fichier téléchargeable)
- **Dépendances :** stdlib `hashlib` uniquement
- **Implémentation :** fonction inline dans `main.py` (trop simple pour un module séparé)

### QR Code

- **Endpoint generate :** `POST /qr/generate` — texte → PNG
- **Endpoint read :** `POST /qr/read` — image → JSON `{"data": "..."}`
- **Dépendances :** `qrcode[pil]`, `pyzbar` + `libzbar0` (apt, Dockerfile)
- **Implémentation :** `compressors/qr.py` avec `generate_qr(text, out)` et `read_qr(path)`

---

## Dépendances à ajouter

| Package | Groupe | Raison |
|---------|--------|--------|
| `qrcode[pil]` | sp3-media-utils | génération QR |
| `pyzbar` | sp3-media-utils | lecture QR |
| `libzbar0` (apt) | sp3-media-utils | dépendance système de pyzbar |

`requirements.txt` et `Dockerfile` mis à jour dans `feat/sp3-media-utils`.

---

## Architecture fichiers

```
compressors/
  pdf/
    tools.py          ← extract_pdf_images, add_pdf_signature ajoutés
  image/
    filters.py        ← nouveau : watermark_image, apply_filter, upscale_image
  media/
    video.py          ← extract_audio, extract_thumbnails ajoutés
  qr.py              ← nouveau : generate_qr, read_qr
main.py               ← nouvelles routes /pdf/, /image/, /video/, /utils/, /qr/
```

---

## Tests

Chaque groupe livre ses tests dans `tests/test_endpoints.py` (routes) et `tests/test_compressors.py` (fonctions). Les outils ffmpeg-dépendants (`extract_audio`, `extract_thumbnails`) sont testés avec `allow_500=True` si ffmpeg absent localement.
