#!/bin/bash
# Télécharge FFmpeg statique au démarrage sur SAP BTP Cloud Foundry.
# Le filesystem CF est éphémère — ce script est appelé avant gunicorn.
# Source : https://github.com/yt-dlp/FFmpeg-Builds (binaires statiques Linux x86_64)
#
# Pour mettre à jour : changer FFMPEG_TAG + FFMPEG_SHA256
#   1. Trouver le tag : https://github.com/yt-dlp/FFmpeg-Builds/releases
#   2. Télécharger l'archive et calculer : sha256sum ffmpeg-master-latest-linux64-gpl.tar.xz
#   3. Mettre à jour les deux variables ci-dessous

set -euo pipefail

FFMPEG_TAG="autobuild-2026-09-30-00-16"
FFMPEG_SHA256="0019dfc4b32d63c1392aa264aed2253c1e0c2fb09216f8e2cc269bbfb8bb49b5"
FFMPEG_URL="https://github.com/yt-dlp/FFmpeg-Builds/releases/download/${FFMPEG_TAG}/ffmpeg-master-latest-linux64-gpl.tar.xz"
BIN_DIR="$(dirname "$0")/../bin"
FFMPEG_BIN="$BIN_DIR/ffmpeg"

mkdir -p "$BIN_DIR"

if [ -f "$FFMPEG_BIN" ]; then
    echo "[fetch_ffmpeg] ffmpeg déjà présent, skip."
    exit 0
fi

echo "[fetch_ffmpeg] Téléchargement FFmpeg (tag: ${FFMPEG_TAG})..."
curl -L --silent --show-error --fail "$FFMPEG_URL" -o /tmp/ffmpeg.tar.xz

echo "[fetch_ffmpeg] Vérification intégrité SHA-256..."
echo "${FFMPEG_SHA256}  /tmp/ffmpeg.tar.xz" | sha256sum -c -
if [ $? -ne 0 ]; then
    echo "[fetch_ffmpeg] ERREUR: SHA-256 invalide — abandon." >&2
    rm -f /tmp/ffmpeg.tar.xz
    exit 1
fi

echo "[fetch_ffmpeg] Extraction..."
tar -xJf /tmp/ffmpeg.tar.xz -C /tmp --strip-components=2 --wildcards "*/bin/ffmpeg"
mv /tmp/ffmpeg "$FFMPEG_BIN"
chmod +x "$FFMPEG_BIN"
rm -f /tmp/ffmpeg.tar.xz

test -x "$FFMPEG_BIN" || { echo "[fetch_ffmpeg] ERREUR: binaire non exécutable." >&2; exit 1; }

echo "[fetch_ffmpeg] OK — $("$FFMPEG_BIN" -version 2>&1 | head -1)"
