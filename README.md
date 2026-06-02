# CompressIt

**Outils fichiers gratuits, 100% locaux — images, PDF, vidéos, archives.**

[![Release](https://img.shields.io/github/v/release/Enzo0673/compressit?label=t%C3%A9l%C3%A9charger&style=for-the-badge&color=0D9488)](https://github.com/Enzo0673/compressit/releases/latest)
[![License: MIT](https://img.shields.io/badge/licence-MIT-green?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/github/actions/workflow/status/Enzo0673/compressit/test.yml?style=for-the-badge&label=tests)](https://github.com/Enzo0673/compressit/actions)

> 🖥️ **[Essayer en ligne](https://compressit-w0ro.onrender.com)** · 📥 **[Télécharger l'app locale](https://github.com/Enzo0673/compressit/releases/latest)**

![Aperçu CompressIt](docs/screenshot.png)

---

## ⬇️ Télécharger l'application

| Plateforme | Lien |
|---|---|
| **Windows** | [CompressIt.exe](https://github.com/Enzo0673/compressit/releases/latest/download/CompressIt.exe) |
| **macOS** | [CompressIt-macOS.zip](https://github.com/Enzo0673/compressit/releases/latest/download/CompressIt-macOS.zip) |
| **Linux** | [CompressIt-Linux.tar.gz](https://github.com/Enzo0673/compressit/releases/latest/download/CompressIt-Linux.tar.gz) |

Double-cliquez sur l'exécutable → l'application s'ouvre dans votre navigateur. **Aucune installation requise.**

> Une version en ligne est également disponible pour tester sans rien installer — les fichiers transitent alors par notre serveur et sont supprimés après 1h.

---

## Outils disponibles

### Multi-fichiers
- **Compression en lot** — Compresser jusqu'à 20 fichiers (images + PDF) en une fois, télécharger un ZIP

### PDF (14 outils)
| Outil | Description |
|---|---|
| Compresser PDF | Réduire le poids d'un PDF |
| Fusionner PDF | Combiner plusieurs PDF en un seul |
| Diviser PDF | Extraire des pages ou découper un PDF |
| PDF → JPG | Convertir chaque page en image JPG |
| JPG → PDF | Assembler des images en PDF |
| Rotation PDF | Faire pivoter des pages |
| Filigrane PDF | Ajouter un texte en filigrane |
| Numéroter pages | Ajouter des numéros de page |
| Supprimer pages | Retirer des pages d'un PDF |
| Déverrouiller PDF | Supprimer la protection par mot de passe |
| Protéger PDF | Ajouter un mot de passe |
| Réparer PDF | Reconstruire un PDF corrompu |
| Extraire texte | Copier le texte d'un PDF natif |
| Word / Excel → PDF | Convertir .docx, .xlsx, .pptx en PDF (nécessite LibreOffice) |

### Images (5 outils)
| Outil | Description |
|---|---|
| Compresser image | Réduire le poids — JPEG, PNG, WebP, GIF, BMP, TIFF |
| Redimensionner | Changer les dimensions |
| Convertir format | Passer d'un format à un autre |
| Recadrer | Rogner une image |
| Rotation / Flip | Faire pivoter ou retourner |

### Vidéo
- **Compresser vidéo** — MP4, MOV, AVI, MKV, WebM (codecs H.264 / H.265 / VP9), progression en temps réel
- **Éditer vidéo** — Découper (trim) et redimensionner

### Archives
- **Compresser archive** — ZIP, 7z, RAR, TAR, GZ, BZ2, ZST (algorithmes zstd, lzma, gzip, brotli)

---

## Pourquoi CompressIt ?

Les outils en ligne comme iLovePDF ou Smallpdf envoient vos fichiers sur leurs serveurs. Avec l'app locale, CompressIt tourne entièrement sur votre machine :

- **100% local** — vos fichiers ne transitent jamais par internet (app locale)
- **Aucun compte requis** — pas d'inscription, pas de limite de taille
- **Open source** — le code est auditable
- **PWA** — installable comme une app, fonctionne hors-ligne
- **Dark mode** — thème clair/sombre, persisté en localStorage
- **Comparaison avant/après** — slider interactif sur les images compressées
- **Téléchargement automatique** — le fichier se télécharge dès la compression terminée

---

## Développement

### Prérequis

- Python 3.10+
- FFmpeg dans le PATH (compression vidéo)
- Poppler (PDF → JPG) : `apt install poppler-utils` / `brew install poppler` / [Windows](https://github.com/oschwartz10612/poppler-windows/releases)

### Démarrage

```bash
git clone https://github.com/Enzo0673/compressit.git
cd compressit
pip install -r requirements.txt
py main.py        # Windows
python main.py    # Linux / Mac
```

### Build de l'exécutable

```bash
pip install pyinstaller

# Placer les binaires FFmpeg + Poppler dans bin/
# (voir compressit.spec pour les noms attendus)

pyinstaller compressit.spec
# → dist/CompressIt.exe (Windows) ou dist/CompressIt (Mac/Linux)
```

Les builds sont automatisés via GitHub Actions à chaque tag `v*`.

---

## Stack technique

| Composant | Technologie |
|---|---|
| Backend | Python 3, FastAPI, Uvicorn |
| Images | Pillow |
| PDF | pikepdf, pdf2image, pdfminer.six |
| Vidéo | ffmpeg-python + FFmpeg (SSE progress) |
| Archives | zstandard, brotli, lzma, gzip |
| Frontend | HTML / CSS / JavaScript vanilla |
| Aperçu PDF | pdf.js (servi en local) |
| PWA | Service Worker + manifest.json |
| Analytics | Umami (sans cookie, RGPD) |
| Build | PyInstaller + GitHub Actions |

---

## Sécurité

Un audit de sécurité complet a été réalisé via la méthodologie **OWASP Risk Rating** avec les [Anthropic Cybersecurity Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills) (`performing-web-application-vulnerability-triage` + `performing-web-application-penetration-test`).

13 vulnérabilités identifiées et corrigées sur 2 passes d'audit (commits `f41bd80`, `d6ea1a5`, `d3fa307`) :

| Sévérité | Vulnérabilité | CWE | OWASP 2021 |
|---|---|---|---|
| 🔴 Critique | Injection `font_color` → FFmpeg drawtext | CWE-78 | A03 - Injection |
| 🟠 Élevé | Path traversal sur `/tool/{name}` | CWE-22 | A01 - Broken Access Control |
| 🟠 Élevé | Bug `download_id` Office to PDF | CWE-706 | A04 - Insecure Design |
| 🟠 Élevé | Rate limiter fuite mémoire (multi-worker) | CWE-400 | A05 - Misconfiguration |
| 🟠 Élevé | Security headers manquants (CSP, HSTS…) | CWE-693 | A05 - Misconfiguration |
| 🟠 Élevé | PDF Stream Injection via `\n` dans le texte watermark | CWE-74 | A03 - Injection |
| 🟠 Élevé | DOM XSS via `clip.name` injecté dans `innerHTML` | CWE-79 | A03 - Injection |
| 🟡 Modéré | `/status` exposait infos système en prod | CWE-200 | A02 - Info Exposure |
| 🟡 Modéré | `watermark text` non borné en longueur | CWE-20 | A03 - Injection |
| 🟡 Modéré | `opacity` et `dpi` non validés | CWE-20 | A03 - Injection |
| 🟡 Modéré | `ranges` PDF split non validé | CWE-20 | A03 - Injection |
| 🟡 Modéré | `position` page-numbers sans whitelist | CWE-20 | A03 - Injection |
| 🟡 Modéré | `font_color` validé uniquement côté compresseur (defense-in-depth manquante) | CWE-20 | A03 - Injection |

Mesures en place :

- CORS restreint à `localhost`
- Validation stricte des paramètres côté serveur (whitelists codec, DPI, qualité, couleur…)
- Protection path traversal sur les téléchargements et les routes outils
- Protection zip bomb sur les archives (ratio, taille décompressée)
- Fichiers temporaires supprimés automatiquement après 1 heure
- Security headers HTTP sur toutes les réponses (`X-Frame-Options`, `X-Content-Type-Options`, `CSP`, `HSTS`, `Referrer-Policy`, `Permissions-Policy`)
- Endpoint `/status` désactivé en production
- Aucune stack trace exposée au client

---

## Licence

[MIT](LICENSE)
