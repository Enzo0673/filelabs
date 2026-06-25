# FileLabs

**26 outils fichiers gratuits, 100% locaux — PDF, images, vidéos, archives.**

[![Release](https://img.shields.io/github/v/release/Enzo0673/filelabs?label=télécharger&style=for-the-badge&color=1A56F0)](https://github.com/Enzo0673/filelabs/releases/latest)
[![License: MIT](https://img.shields.io/badge/licence-MIT-1A56F0?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/github/actions/workflow/status/Enzo0673/filelabs/test.yml?style=for-the-badge&label=tests)](https://github.com/Enzo0673/filelabs/actions)

> **[Essayer en ligne](https://filelabs.onrender.com)** · **[Télécharger l'app locale](https://github.com/Enzo0673/filelabs/releases/latest)**

---

## Pourquoi FileLabs ?

Les outils en ligne comme iLovePDF ou Smallpdf envoient vos fichiers sur leurs serveurs. FileLabs fonctionne entièrement sur votre machine — aucune donnée ne quitte votre ordinateur.

| | FileLabs | Concurrents |
|---|:---:|:---:|
| 100% local (app) | ✅ | ❌ |
| Aucun compte requis | ✅ | ❌ |
| Open source | ✅ | ❌ |
| Hors-ligne (PWA) | ✅ | ❌ |
| Sans limite de taille (app) | ✅ | ❌ |

---

## Outils disponibles (26)

### Multi-fichiers
- **Compression en lot** — Compresser jusqu'à 20 fichiers en une fois, télécharger un ZIP

### PDF — 14 outils

| Outil | Description |
|---|---|
| Fusionner PDF | Combiner plusieurs PDF en un seul |
| Diviser PDF | Extraire des pages ou découper un PDF |
| Compresser PDF | Réduire le poids d'un PDF |
| PDF → JPG | Convertir chaque page en image |
| JPG → PDF | Assembler des images en PDF |
| Rotation PDF | Pivoter des pages individuellement ou tout le document |
| Filigrane PDF | Ajouter un texte en filigrane (position, couleur, opacité) |
| Numéroter pages | Ajouter des numéros en bas ou en haut |
| Supprimer pages | Retirer des pages par numéro ou plage |
| Déverrouiller PDF | Supprimer la protection par mot de passe |
| Protéger PDF | Ajouter un mot de passe AES-256 |
| Réparer PDF | Reconstruire un PDF corrompu |
| Extraire texte | Copier le texte d'un PDF natif |
| Word / Excel → PDF | Convertir .docx, .xlsx, .pptx (nécessite LibreOffice) |

### Images — 5 outils

| Outil | Description |
|---|---|
| Compresser image | JPEG, PNG, WebP, GIF, BMP, TIFF |
| Redimensionner | Changer les dimensions en pixels |
| Convertir format | JPG, PNG, WebP, BMP… |
| Recadrer | Rogner une zone de l'image |
| Rotation / Flip | Pivoter ou retourner l'image |

### Vidéo — 5 outils

| Outil | Description |
|---|---|
| Compresser vidéo | MP4, MOV, AVI, MKV, WebM · H.264 / H.265 / VP9 · progression temps réel |
| Éditer vidéo | Découper (trim), redimensionner, fusionner, ajouter texte/sous-titres |
| Video Downloader | YouTube, TikTok, Instagram… en MP4 ou MP3 |
| Image Downloader | Extraire les images depuis Instagram, Pinterest, Twitter/X… |
| Vidéo vers texte | Transcrire l'audio d'une vidéo |

### Archives — 1 outil

- **Compresser archive** — ZIP, 7z, RAR, TAR, GZ, BZ2, ZST · algorithmes zstd, lzma, gzip, brotli

---

## Télécharger l'application

| Plateforme | Lien |
|---|---|
| **Windows** | [FileLabs.exe](https://github.com/Enzo0673/filelabs/releases/latest/download/FileLabs.exe) |
| **macOS** | [FileLabs-macOS.zip](https://github.com/Enzo0673/filelabs/releases/latest/download/FileLabs-macOS.zip) |
| **Linux** | [FileLabs-Linux.tar.gz](https://github.com/Enzo0673/filelabs/releases/latest/download/FileLabs-Linux.tar.gz) |

Double-cliquez sur l'exécutable → l'application s'ouvre dans votre navigateur. Aucune installation requise.

> Une version en ligne est disponible pour tester sans rien installer — les fichiers transitent alors par notre serveur et sont supprimés automatiquement après 1h.

---

## Développement

### Prérequis

- Python 3.10+
- FFmpeg dans le PATH (compression vidéo)
- Poppler (PDF → JPG) : `apt install poppler-utils` / `brew install poppler` / [Windows builds](https://github.com/oschwartz10612/poppler-windows/releases)
- LibreOffice (optionnel, pour Word/Excel → PDF)

### Démarrage

```bash
git clone https://github.com/Enzo0673/filelabs.git
cd filelabs
pip install -r requirements.txt
py main.py        # Windows
python main.py    # Linux / Mac
```

Ouvre automatiquement `http://localhost:8000` dans votre navigateur.

### Tests

```bash
pytest tests/
```

### Build exécutable

```bash
pip install pyinstaller
# Placer les binaires FFmpeg + Poppler dans bin/
pyinstaller filelabs.spec
# → dist/FileLabs.exe (Windows) ou dist/FileLabs (Mac/Linux)
```

Les builds sont automatisés via GitHub Actions à chaque tag `v*`.

---

## Stack technique

| Composant | Technologie |
|---|---|
| Backend | Python 3, FastAPI, Uvicorn |
| Images | Pillow |
| PDF | pikepdf, pdf2image, pdfminer.six |
| Vidéo | ffmpeg-python + FFmpeg (SSE progress), yt-dlp |
| Archives | zstandard, brotli, lzma, gzip |
| Frontend | HTML / CSS / JavaScript vanilla |
| Design | Playfair Display + Space Mono · design system "Cream & Ink" |
| Aperçu PDF | pdf.js (servi en local) |
| PWA | Service Worker + manifest.json |
| Analytics | Umami (sans cookie, RGPD) |
| Build | PyInstaller + GitHub Actions |

---

## Sécurité

Audit complet via la méthodologie **OWASP Risk Rating** — 26 vulnérabilités identifiées et corrigées.

**Mesures en place :**

- Protection SSRF — validation schéma + résolution DNS avec blocage de toutes les plages IP privées
- Rate limiting en production (Render) : 20 req/min par IP réelle (`X-Forwarded-For`)
- Max 3 téléchargements simultanés, timeout 10 min
- Validation stricte des paramètres côté serveur (whitelists codec, DPI, qualité, couleur, format…)
- Magic bytes validation sur tous les uploads
- Protection path traversal sur les téléchargements et les routes outils
- Protection zip bomb (ratio, taille décompressée)
- Security headers HTTP sur toutes les réponses (CSP, HSTS, X-Frame-Options…)
- Fichiers temporaires supprimés automatiquement après 1h
- Aucune stack trace exposée au client

---

## Licence

[MIT](LICENSE)
