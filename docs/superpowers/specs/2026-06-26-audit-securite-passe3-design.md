# Audit Sécurité — 3e Passe (FileLabs)

**Date :** 2026-06-26
**Périmètre :** Nouveaux outils depuis la passe 2 — `video-downloader`, `image-downloader`, `video-to-text` + passage au traitement 100% local côté client
**Méthode :** 4 agents parallèles, chacun avec un skill cybersécurité spécialisé

---

## Contexte

Les passes 1 et 2 ont corrigé 13 vulnérabilités. Depuis, trois outils ont été ajoutés :

- `video-downloader` — Télécharge depuis YouTube/TikTok via yt-dlp, routes `/video/download/*`
- `image-downloader` — Télécharge des images depuis Instagram/Pinterest via yt-dlp, routes `/media/*`
- `video-to-text` — Transcription Whisper (faster-whisper), route `/video/to-text`

Deux changements architecturaux majeurs élargissent la surface d'attaque :

1. Le traitement pour certains outils est désormais 100% côté client (JS/wasm) — les `processors/*.js` gèrent image, PDF, archive, vidéo sans upload serveur.
2. Les outils downloader introduisent des URL utilisateur passées à un sous-processus externe (yt-dlp).

---

## Findings identifiés (pré-audit, analyse statique)

| # | Vulnérabilité | Sévérité | Fichier | Ligne | CWE |
|---|---------------|----------|---------|-------|-----|
| 1 | SSRF : `img_url` issu de yt-dlp passé à yt-dlp sans re-validation SSRF | **Élevé** | `compressors/image/downloader.py` | 159 | CWE-918 |
| 2 | Rate limit absent sur `/media/info` et `/media/download` | **Élevé** | `main.py` | 148 | CWE-400 |
| 3 | XSS DOM via `innerHTML` avec `seg.text` (données Whisper) | **Modéré** | `static/tools/video-to-text.html` | 291 | CWE-79 |
| 4 | XSS DOM via `innerHTML` avec `fmt.label` (données yt-dlp) | **Modéré** | `static/tools/video-downloader.html` | 326 | CWE-79 |
| 5 | DNS rebinding TOCTOU : gap entre `_validate_url()` et résolution yt-dlp | **Faible** | `compressors/media/downloader.py` | 36 | CWE-918 |
| 6 | Magic bytes absents sur `/video/to-text` (validation extension seulement) | **Faible** | `main.py` | 1378 | CWE-20 |

---

## Architecture de l'audit

### Exécution — 4 agents en parallèle

```
Claude Code (orchestrateur)
├── Agent 1 — SSRF          skill: exploiting-server-side-request-forgery
│   cibles: compressors/media/downloader.py, compressors/image/downloader.py
│   focus: img_url non validé (finding #1), DNS rebinding TOCTOU (finding #5)
│   output: findings.ssrf.md + patches directs
│
├── Agent 2 — XSS           skill: testing-for-xss-vulnerabilities
│   cibles: static/tools/video-to-text.html, static/tools/video-downloader.html
│   focus: innerHTML seg.text (#3), innerHTML fmt.label (#4)
│   output: findings.xss.md + patches directs
│
├── Agent 3 — Input/DoS     skill: performing-web-application-vulnerability-triage
│   cibles: main.py (routes /video/to-text, /media/*, /video/download)
│   focus: magic bytes (#6), indices négatifs, dict _download_progress borné
│   output: findings.input.md + patches directs
│
└── Agent 4 — Rate Limit    skill: detecting-api-enumeration-attacks
    cibles: main.py (middleware, _PROCESSING_PATHS)
    focus: /media/ absent du rate limiter (#2), SSE endpoint illimité
    output: findings.ratelimit.md + patches directs
```

### Consolidation (orchestrateur)

1. Collecter les 4 rapports findings.*.md
2. Appliquer les patches dans l'ordre : SSRF et rate limit en premier (sévérité élevée), puis XSS, puis faibles
3. Vérifier qu'il n'y a pas de conflits entre patches
4. Lancer les tests (`pytest`) pour valider
5. Un commit par catégorie de fix (SSRF, XSS, input, ratelimit)
6. Mettre à jour la mémoire projet avec les 6 nouvelles vulnérabilités corrigées

---

## Périmètre exact des agents

### Agent 1 — SSRF
**Fichiers à lire :**
- `compressors/image/downloader.py` (entier)
- `compressors/media/downloader.py` (entier)

**Findings à confirmer ou invalider :**
- F1 : `download_images()` ligne 159 — `img_url` vient de la réponse yt-dlp JSON, est passé directement à un second appel yt-dlp subprocess sans appeler `_validate_url()`. Un serveur contrôlé par un attaquant (via une plateforme custom) pourrait retourner une URL interne.
- F5 : TOCTOU entre `_validate_url()` (résolution DNS au moment de la validation) et l'exécution de yt-dlp (résolution DNS propre, potentiellement différente). TTL court + DNS rebinding possible.

**Patches attendus :**
- F1 : Appeler `_validate_url(img_url)` avant de le passer à yt-dlp dans `download_images()`
- F5 : Documenter la limitation (DNS rebinding est difficile à résoudre entièrement sans proxy DNS), ou ajouter un `--source-address` yt-dlp si possible

### Agent 2 — XSS
**Fichiers à lire :**
- `static/tools/video-to-text.html` (lignes 280–300)
- `static/tools/video-downloader.html` (lignes 320–340)

**Findings à confirmer ou invalider :**
- F3 : `row.innerHTML = \`...<div class="seg-text">${seg.text.trim()}</div>\`` — `seg.text` est du texte brut issu de Whisper, mais passé via `innerHTML`. Si Whisper retourne `<img onerror=...>` dans la transcription, XSS exécutable.
- F4 : `btn.innerHTML = \`<span ...>🎬</span>${fmt.label}\`` — `fmt.label` vient de yt-dlp JSON. Valeurs attendues : "1080p", "720p" etc., mais techniquement non sanitisées.

**Patches attendus :**
- F3 : Remplacer `innerHTML` par `textContent` pour `seg.text` (créer l'élément proprement)
- F4 : Remplacer `innerHTML` par création DOM sécurisée pour `fmt.label`

### Agent 3 — Input Validation & DoS
**Fichiers à lire :**
- `main.py` lignes 1365–1402 (video/to-text)
- `main.py` lignes 1180–1214 (media/download)
- `main.py` lignes 250–260 (_download_progress)

**Findings à confirmer ou invalider :**
- F6 : `/video/to-text` valide l'extension (`.mp4`, `.mkv`…) mais pas les magic bytes. Un fichier malformé ou un type non-média avec extension `.mp4` est accepté et passé à Whisper/ffmpeg.
- Bonus : `indices: list[int]` — vérifier que les indices négatifs sont bien filtrés (ils le sont en `if 0 <= idx < len(images)` mais confirmation formelle souhaitée)
- Bonus : `_download_progress` dict — confirmer qu'il ne peut pas grossir indéfiniment

**Patches attendus :**
- F6 : Ajouter validation magic bytes pour les fichiers vidéo/audio (ex. vérifier les 12 premiers octets)

### Agent 4 — Rate Limiting
**Fichiers à lire :**
- `main.py` lignes 140–170 (middleware rate limit)

**Findings à confirmer ou invalider :**
- F2 : `_PROCESSING_PATHS = ("/compress", "/pdf/", "/image/", "/video/", "/download/")` — `/media/` est absent. Les routes `/media/info` et `/media/download` ne sont pas soumises au rate limit sur Render.
- Bonus : `/video/download/progress/{uid}` (SSE) — pas de rate limit sur le polling SSE. Un attacker pourrait ouvrir de nombreuses connexions SSE.

**Patches attendus :**
- F2 : Ajouter `"/media/"` dans `_PROCESSING_PATHS`
- Bonus SSE : Optionnellement limiter le polling SSE (déjà protégé partiellement par `_validate_uid`)

---

## Critères de succès

- Les 6 findings sont soit corrigés, soit documentés comme accepted risk avec justification
- `pytest` passe après les patches
- Chaque fix a un commit propre avec message de type `fix(security): ...`
- La mémoire projet est mise à jour avec le nombre total de vulns corrigées (13 + nouvelles)

---

## Hors périmètre (pour cet audit)

- Les outils existants déjà audités en passe 1 et 2 (sauf si un agent identifie une régression)
- Les processors JS côté client (`static/js/processors/`) — opèrent sur des données locales uniquement, surface d'attaque limitée
- Les dépendances tierces (yt-dlp, faster-whisper) — hors contrôle direct
