#!/bin/bash
# Télécharge FFmpeg statique au démarrage sur SAP BTP Cloud Foundry.
# Le filesystem CF est éphémère — ce script est appelé avant gunicorn.
# Source : https://github.com/yt-dlp/FFmpeg-Builds (binaires statiques Linux x86_64)

FFMPEG_URL="https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
BIN_DIR="$(dirname "$0")/../bin"
FFMPEG_BIN="$BIN_DIR/ffmpeg"

mkdir -p "$BIN_DIR"

if [ -f "$FFMPEG_BIN" ]; then
    echo "[fetch_ffmpeg] ffmpeg déjà présent, skip."
    exit 0
fi

echo "[fetch_ffmpeg] Téléchargement FFmpeg..."
curl -L --silent --show-error --fail "$FFMPEG_URL" -o /tmp/ffmpeg.tar.xz

echo "[fetch_ffmpeg] Extraction..."
tar -xJf /tmp/ffmpeg.tar.xz -C /tmp --strip-components=2 --wildcards "*/bin/ffmpeg"
mv /tmp/ffmpeg "$FFMPEG_BIN"
chmod +x "$FFMPEG_BIN"
rm -f /tmp/ffmpeg.tar.xz

echo "[fetch_ffmpeg] OK — $(${FFMPEG_BIN} -version 2>&1 | head -1)"
