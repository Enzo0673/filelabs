# Audit Sécurité Passe 3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger 6 vulnérabilités identifiées dans les outils video-downloader, image-downloader et video-to-text ajoutés depuis la passe 2.

**Architecture:** 4 fixes Python/HTML indépendants, applicables dans n'importe quel ordre ; un test pytest par fix Python ; commits séparés par catégorie. Les fixes HTML sont vérifiés manuellement par inspection de code.

**Tech Stack:** Python 3.x, FastAPI, pytest, HTML/JavaScript vanilla (pas de framework JS)

---

## Fichiers touchés

| Fichier | Action | Raison |
|---------|--------|--------|
| `compressors/image/downloader.py` | Modifier ligne 158-163 | F1 — SSRF : ajouter `_validate_url(img_url)` |
| `main.py` | Modifier ligne 148 | F2 — Rate limit : ajouter `/media/` dans `_PROCESSING_PATHS` |
| `main.py` | Ajouter ~ligne 1354 | F6 — Magic bytes : fonction `_is_exec_magic()` + check dans `/video/to-text` |
| `static/tools/video-to-text.html` | Modifier lignes 289-292 | F3 — XSS : `innerHTML` → `textContent` |
| `static/tools/video-downloader.html` | Modifier ligne 326 | F4 — XSS : `innerHTML` → création DOM sécurisée |
| `tests/test_compressors.py` | Ajouter en fin de fichier | Tests pour F1, F2, F6 |

---

## Task 1 : Fix SSRF — valider `img_url` dans `download_images()`

**Contexte :** Dans `compressors/image/downloader.py`, la fonction `download_images()` récupère les URLs d'images depuis la sortie JSON de yt-dlp (`img_url = img["url"]`), puis les passe directement à un second sous-processus yt-dlp. Ces URLs ne sont pas validées contre les réseaux internes, ce qui permet théoriquement un SSRF si une plateforme retourne une URL interne.

**Fix :** Appeler `_validate_url(img_url)` avant chaque appel subprocess dans la boucle.

**Files:**
- Modify: `compressors/image/downloader.py:158-163`
- Test: `tests/test_compressors.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à la fin de `tests/test_compressors.py` :

```python
# ─── SSRF — _validate_url dans download_images ──────────────────────────────

from compressors.image.downloader import _validate_url
from compressors.media.downloader import DownloaderError

def test_validate_url_blocks_private_ip():
    """_validate_url doit rejeter les IPs privées."""
    with pytest.raises(DownloaderError, match="non autorisée"):
        _validate_url("http://192.168.1.1/image.jpg")

def test_validate_url_blocks_loopback():
    with pytest.raises(DownloaderError, match="non autorisée"):
        _validate_url("http://127.0.0.1/image.jpg")

def test_validate_url_blocks_metadata_service():
    """Bloquer l'IP du metadata service cloud AWS."""
    with pytest.raises(DownloaderError):
        _validate_url("http://169.254.169.254/latest/meta-data/")

def test_validate_url_rejects_non_http():
    with pytest.raises(DownloaderError, match="http"):
        _validate_url("file:///etc/passwd")

def test_validate_url_rejects_ftp():
    with pytest.raises(DownloaderError, match="http"):
        _validate_url("ftp://example.com/image.jpg")
```

- [ ] **Step 2 : Vérifier que les tests passent déjà** (ils testent `_validate_url` existante)

```bash
cd "C:\Users\I768882\OneDrive - SAP SE\Desktop\filelabs"
C:\Windows\py.exe -m pytest tests/test_compressors.py::test_validate_url_blocks_private_ip tests/test_compressors.py::test_validate_url_blocks_loopback tests/test_compressors.py::test_validate_url_blocks_metadata_service tests/test_compressors.py::test_validate_url_rejects_non_http tests/test_compressors.py::test_validate_url_rejects_ftp -v
```

Expected : 5 PASSED (la fonction `_validate_url` existe déjà et fonctionne).

- [ ] **Step 3 : Écrire un test d'intégration ciblant le bug F1**

Ce test vérifie que `download_images()` appelle bien `_validate_url` sur les URLs internes d'images (le bug était que `img_url` n'était pas validé). On mocke `get_media_info` pour retourner une URL interne.

Ajouter dans `tests/test_compressors.py` :

```python
from unittest.mock import patch, MagicMock

def test_download_images_validates_img_url():
    """download_images() doit rejeter les img_url pointant vers des IPs privées."""
    import tempfile
    from pathlib import Path
    from compressors.image.downloader import download_images

    fake_info = {
        "title": "Test",
        "images": [{"index": 0, "thumbnail": "http://192.168.1.1/img.jpg",
                     "ext": "jpg", "url": "http://192.168.1.1/img.jpg"}],
    }
    with patch("compressors.image.downloader.get_media_info", return_value=fake_info):
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(DownloaderError):
                download_images("https://www.instagram.com/p/abc/", [0], Path(tmp))
```

- [ ] **Step 4 : Lancer le test pour vérifier qu'il échoue (bug confirmé)**

```bash
C:\Windows\py.exe -m pytest tests/test_compressors.py::test_download_images_validates_img_url -v
```

Expected : FAIL — `DownloaderError` n'est pas levée car `img_url` n'est pas validée.

- [ ] **Step 5 : Appliquer le fix dans `compressors/image/downloader.py`**

Lire le fichier, puis remplacer la boucle à partir de la ligne 158 :

**Avant (lignes 158–163) :**
```python
    for img in selected:
        img_url = img["url"]
        ext = img["ext"]
        dest = output_dir / f"image_{img['index']}.{ext}"
        try:
            dl = subprocess.run(
```

**Après :**
```python
    for img in selected:
        img_url = img["url"]
        _validate_url(img_url)          # CWE-918 : re-valider l'URL issue de yt-dlp
        ext = img["ext"]
        dest = output_dir / f"image_{img['index']}.{ext}"
        try:
            dl = subprocess.run(
```

- [ ] **Step 6 : Lancer tous les tests du fichier**

```bash
C:\Windows\py.exe -m pytest tests/test_compressors.py::test_download_images_validates_img_url tests/test_compressors.py::test_validate_url_blocks_private_ip tests/test_compressors.py::test_validate_url_blocks_loopback -v
```

Expected : 3 PASSED

- [ ] **Step 7 : Commit**

```bash
git add compressors/image/downloader.py tests/test_compressors.py
git commit -m "fix(security): validate img_url against SSRF in download_images() — CWE-918"
```

---

## Task 2 : Fix Rate Limit — couvrir `/media/`

**Contexte :** Le middleware de rate limiting (actif uniquement sur Render/prod) couvre `_PROCESSING_PATHS` qui ne contient pas `/media/`. Les routes `/media/info` et `/media/download` de l'image downloader peuvent être appelées sans restriction de fréquence.

**Files:**
- Modify: `main.py:148`
- Test: `tests/test_compressors.py`

- [ ] **Step 1 : Écrire le test**

Ajouter dans `tests/test_compressors.py` :

```python
# ─── Rate limit — /media/ couvert ──────────────────────────────────────────

def test_processing_paths_includes_media():
    """_PROCESSING_PATHS doit inclure /media/ pour le rate limiting."""
    import main as app_module
    assert "/media/" in app_module._PROCESSING_PATHS, (
        "/media/ absent de _PROCESSING_PATHS — les routes image-downloader "
        "ne sont pas protégées par le rate limiter."
    )
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

```bash
C:\Windows\py.exe -m pytest tests/test_compressors.py::test_processing_paths_includes_media -v
```

Expected : FAIL — `/media/` absent.

- [ ] **Step 3 : Appliquer le fix dans `main.py`**

Ligne 148, remplacer :

```python
_PROCESSING_PATHS = ("/compress", "/pdf/", "/image/", "/video/", "/download/")
```

Par :

```python
_PROCESSING_PATHS = ("/compress", "/pdf/", "/image/", "/video/", "/download/", "/media/")
```

- [ ] **Step 4 : Lancer le test**

```bash
C:\Windows\py.exe -m pytest tests/test_compressors.py::test_processing_paths_includes_media -v
```

Expected : PASSED

- [ ] **Step 5 : Commit**

```bash
git add main.py tests/test_compressors.py
git commit -m "fix(security): add /media/ to rate-limited paths — CWE-400"
```

---

## Task 3 : Fix XSS — `innerHTML` avec `seg.text` dans `video-to-text.html`

**Contexte :** Ligne 291 de `static/tools/video-to-text.html`, `row.innerHTML` utilise `seg.text.trim()` directement. La valeur vient de la réponse JSON de `/video/to-text` (transcription Whisper). Si la transcription contient des balises HTML (ex. `<img src=x onerror=alert(1)>`), elles seront interprétées par le navigateur.

**Files:**
- Modify: `static/tools/video-to-text.html:289-292`

- [ ] **Step 1 : Identifier la ligne exacte**

Ouvrir `static/tools/video-to-text.html`, chercher le bloc :

```javascript
      (data.segments || []).forEach(seg => {
        const row = document.createElement('div');
        row.className = 'seg-row';
        row.innerHTML = `<div class="seg-time">${fmtTime(seg.start)} → ${fmtTime(seg.end)}</div><div class="seg-text">${seg.text.trim()}</div>`;
        list.appendChild(row);
      });
```

- [ ] **Step 2 : Remplacer par une construction DOM sécurisée**

Remplacer le bloc ci-dessus par :

```javascript
      (data.segments || []).forEach(seg => {
        const row = document.createElement('div');
        row.className = 'seg-row';
        const timeDiv = document.createElement('div');
        timeDiv.className = 'seg-time';
        timeDiv.textContent = `${fmtTime(seg.start)} → ${fmtTime(seg.end)}`;
        const textDiv = document.createElement('div');
        textDiv.className = 'seg-text';
        textDiv.textContent = seg.text.trim();
        row.appendChild(timeDiv);
        row.appendChild(textDiv);
        list.appendChild(row);
      });
```

- [ ] **Step 3 : Vérification manuelle**

Rechercher dans `static/tools/video-to-text.html` qu'il n'y a plus aucun `innerHTML` recevant des données issues de `seg.*` ou `data.*` :

```bash
grep -n "innerHTML" "static/tools/video-to-text.html"
```

Expected : seule la ligne `list.innerHTML = '';` doit apparaître (remise à zéro de la liste, pas de données utilisateur).

- [ ] **Step 4 : Commit**

```bash
git add static/tools/video-to-text.html
git commit -m "fix(security): replace innerHTML with textContent for seg.text — CWE-79"
```

---

## Task 4 : Fix XSS — `innerHTML` avec `fmt.label` dans `video-downloader.html`

**Contexte :** Ligne 326 de `static/tools/video-downloader.html`, `btn.innerHTML` inclut `fmt.label` directement. Cette valeur vient de la réponse JSON de `/video/download/info` (champ `label` construit depuis les formats yt-dlp). En pratique les labels sont "1080p", "720p" etc., mais ils proviennent de données externes non sanitisées.

**Files:**
- Modify: `static/tools/video-downloader.html:326`

- [ ] **Step 1 : Identifier la ligne exacte**

Ouvrir `static/tools/video-downloader.html`, chercher :

```javascript
      btn.innerHTML = `<span class="fmt-icon">🎬</span>${fmt.label}`;
```

- [ ] **Step 2 : Remplacer par création DOM sécurisée**

Remplacer cette ligne par :

```javascript
      const icon = document.createElement('span');
      icon.className = 'fmt-icon';
      icon.textContent = '🎬';
      btn.appendChild(icon);
      btn.appendChild(document.createTextNode(fmt.label));
```

- [ ] **Step 3 : Vérification manuelle**

```bash
grep -n "innerHTML" "static/tools/video-downloader.html"
```

Expected : `formatGrid.innerHTML = "";` uniquement (remise à zéro, pas de données externes).

- [ ] **Step 4 : Commit**

```bash
git add static/tools/video-downloader.html
git commit -m "fix(security): replace innerHTML with safe DOM for fmt.label — CWE-79"
```

---

## Task 5 : Fix Input — magic bytes pour `/video/to-text`

**Contexte :** L'endpoint `/video/to-text` valide l'extension du fichier mais pas son contenu réel. Un fichier `.mp4` contenant un exécutable Windows (magic bytes `MZ`) ou un script PHP serait accepté et transmis à Whisper/ffmpeg. Le fix ajoute une liste de deny-list sur les signatures d'exécutables/scripts (approche permissive : on rejette seulement les mauvaises signatures connues, on laisse passer l'inconnu).

**Files:**
- Modify: `main.py` (~ligne 1354, avant `_VALID_WHISPER_MODELS`)
- Modify: `main.py` (~ligne 1385, dans l'endpoint `/video/to-text`)
- Test: `tests/test_compressors.py`

- [ ] **Step 1 : Écrire les tests**

Ajouter dans `tests/test_compressors.py` :

```python
# ─── Magic bytes — /video/to-text ───────────────────────────────────────────

def test_is_exec_magic_rejects_windows_pe():
    import main as app_module
    assert app_module._is_exec_magic(b'\x4d\x5a\x90\x00\x03\x00') is True  # MZ

def test_is_exec_magic_rejects_elf():
    import main as app_module
    assert app_module._is_exec_magic(b'\x7fELF\x02\x01\x01\x00') is True

def test_is_exec_magic_rejects_php():
    import main as app_module
    assert app_module._is_exec_magic(b'<?php echo "hi";') is True

def test_is_exec_magic_rejects_html():
    import main as app_module
    assert app_module._is_exec_magic(b'<html><body>') is True
    assert app_module._is_exec_magic(b'<!DOCTYPE html>') is True

def test_is_exec_magic_accepts_mp3_id3():
    import main as app_module
    assert app_module._is_exec_magic(b'ID3\x03\x00\x00\x00') is False

def test_is_exec_magic_accepts_mkv():
    import main as app_module
    assert app_module._is_exec_magic(b'\x1a\x45\xdf\xa3\x9f') is False

def test_is_exec_magic_accepts_unknown():
    """Un fichier sans signature connue doit passer (permissif)."""
    import main as app_module
    assert app_module._is_exec_magic(b'\x00\x00\x00\x20\x66\x74\x79\x70') is False  # MP4 ftyp
```

- [ ] **Step 2 : Lancer pour vérifier l'échec**

```bash
C:\Windows\py.exe -m pytest tests/test_compressors.py::test_is_exec_magic_rejects_windows_pe -v
```

Expected : FAIL — `_is_exec_magic` n'existe pas encore.

- [ ] **Step 3 : Ajouter la fonction `_is_exec_magic` dans `main.py`**

Lire `main.py` lignes 1354–1360, puis insérer juste avant `_VALID_WHISPER_MODELS` :

```python
# ---- Validation magic bytes (deny-list exécutables/scripts) ----
_EXEC_SIGNATURES: list[bytes] = [
    b'\x4d\x5a',      # Windows PE (MZ)
    b'\x7fELF',       # Linux/Unix ELF
    b'<?php',         # PHP script
    b'<?Ph',          # PHP case variation
    b'<html',         # HTML
    b'<!DOC',         # HTML DOCTYPE
    b'PK\x03\x04',   # ZIP archive (Office, JAR…)
    b'#!/',            # Shell shebang
]

def _is_exec_magic(header: bytes) -> bool:
    """Retourne True si les premiers octets correspondent à un exécutable ou script connu."""
    h = header[:8]
    h_lower = h.lower()
    for sig in _EXEC_SIGNATURES:
        if h_lower.startswith(sig.lower()):
            return True
    return False
```

- [ ] **Step 4 : Appliquer le check dans l'endpoint `/video/to-text`**

Dans `main.py`, dans l'endpoint `video_to_text`, remplacer :

```python
    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["video"])
```

Par :

```python
    # Magic bytes — rejeter les exécutables et scripts déguisés en média
    header = await file.read(8)
    await file.seek(0)
    if _is_exec_magic(header):
        raise HTTPException(status_code=400, detail="Format de fichier non supporté.")

    uid = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{uid}_input{ext}"
    try:
        await _save_upload(file, input_path, MAX_SIZE["video"])
```

- [ ] **Step 5 : Lancer tous les tests magic bytes**

```bash
C:\Windows\py.exe -m pytest tests/test_compressors.py -k "magic" -v
```

Expected : 7 PASSED

- [ ] **Step 6 : Lancer la suite complète pour détecter les régressions**

```bash
C:\Windows\py.exe -m pytest tests/ -v
```

Expected : tous PASSED (ou les mêmes skips qu'avant).

- [ ] **Step 7 : Commit**

```bash
git add main.py tests/test_compressors.py
git commit -m "fix(security): add exec/script magic-bytes deny-list for /video/to-text — CWE-20"
```

---

## Task 6 : Document DNS rebinding (accepted risk)

**Contexte :** Finding F5 — TOCTOU entre `_validate_url()` et la résolution DNS propre de yt-dlp. Un attacker contrôlant un domaine avec TTL très court pourrait changer la résolution entre la validation et l'exécution. En pratique cette attaque est difficile à exploiter (timing précis, yt-dlp timeout 30s) et la mitiguer entièrement nécessiterait un proxy DNS ou un hook yt-dlp non disponible publiquement.

**Files:**
- Modify: `compressors/media/downloader.py` (~ligne 36)

- [ ] **Step 1 : Ajouter un commentaire de documentation dans `_validate_url`**

Lire `compressors/media/downloader.py`, puis remplacer le docstring de `_validate_url` :

**Avant :**
```python
def _validate_url(url: str) -> None:
    """
    Valide l'URL et bloque les IPs privées/internes (SSRF).

    Raises:
        DownloaderError: URL invalide ou IP interne détectée
    """
```

**Après :**
```python
def _validate_url(url: str) -> None:
    """
    Valide l'URL et bloque les IPs privées/internes (SSRF).

    Limitation connue (accepted risk) : TOCTOU DNS rebinding.
    Cette fonction résout le DNS au moment de la validation, mais yt-dlp
    effectue sa propre résolution DNS lors du téléchargement. Un attacker
    contrôlant un domaine avec un TTL très court pourrait changer la résolution
    entre ces deux instants. Atténuants : timing difficile à maîtriser, yt-dlp
    timeout à 30s, et l'attaque nécessite un contrôle DNS externe.
    Mitigation complète : utiliser un proxy DNS filtrant (hors périmètre).

    Raises:
        DownloaderError: URL invalide ou IP interne détectée
    """
```

- [ ] **Step 2 : Commit**

```bash
git add compressors/media/downloader.py
git commit -m "docs(security): document DNS rebinding TOCTOU as accepted risk in _validate_url"
```

---

## Task 7 : Rapport final et mise à jour mémoire

- [ ] **Step 1 : Vérifier que tous les fixes sont en place**

```bash
# Vérifier F1 — img_url validée
grep -n "_validate_url(img_url)" compressors/image/downloader.py

# Vérifier F2 — /media/ dans _PROCESSING_PATHS
grep -n "_PROCESSING_PATHS" main.py

# Vérifier F3 — plus de innerHTML avec seg.text
grep -n "innerHTML" static/tools/video-to-text.html

# Vérifier F4 — plus de innerHTML avec fmt.label
grep -n "innerHTML" static/tools/video-downloader.html

# Vérifier F5 — commentaire accepted risk
grep -n "TOCTOU" compressors/media/downloader.py

# Vérifier F6 — _is_exec_magic présente
grep -n "_is_exec_magic" main.py
```

- [ ] **Step 2 : Suite de tests complète**

```bash
C:\Windows\py.exe -m pytest tests/ -v
```

Expected : tous PASSED.

- [ ] **Step 3 : Mettre à jour le README — compteur de vulnérabilités**

Dans `README.md`, chercher la mention des 13 vulnérabilités corrigées et mettre à jour le compteur :

```bash
grep -n "vulnérabilité\|vulnerabilit\|vuln\|sécurité" README.md
```

Puis mettre à jour la ligne correspondante : **13 → 19 vulnérabilités corrigées** (13 passes 1+2, + 6 cette passe).

- [ ] **Step 4 : Commit final**

```bash
git add README.md
git commit -m "docs: update security audit count to 19 (passe 3 — 6 new fixes)"
```

---

## Récapitulatif des findings et fixes

| # | Sévérité | Finding | Fix | Task |
|---|----------|---------|-----|------|
| F1 | **Élevé** | SSRF `img_url` non validé | `_validate_url(img_url)` dans `download_images()` | Task 1 |
| F2 | **Élevé** | Rate limit absent `/media/` | Ajouter `"/media/"` dans `_PROCESSING_PATHS` | Task 2 |
| F3 | **Modéré** | XSS DOM `innerHTML seg.text` | Construction DOM avec `textContent` | Task 3 |
| F4 | **Modéré** | XSS DOM `innerHTML fmt.label` | `document.createTextNode(fmt.label)` | Task 4 |
| F5 | **Faible** | DNS rebinding TOCTOU | Accepted risk documenté | Task 6 |
| F6 | **Faible** | Magic bytes absents `/video/to-text` | `_is_exec_magic()` deny-list | Task 5 |
