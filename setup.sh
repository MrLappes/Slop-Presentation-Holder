#!/bin/bash
# Agentic Shield — Presentation Setup
# Creates venv, installs deps, downloads 4 German TTS voice models

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  Agentic Shield — Setup"
echo "============================================"
echo

# 1. System dependency (espeak-ng needed by piper-phonemize)
if ! command -v espeak-ng &>/dev/null; then
    echo "[1/3] Installing espeak-ng (needed for phonemization)..."
    if command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm espeak-ng
    elif command -v apt &>/dev/null; then
        sudo apt install -y espeak-ng
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y espeak-ng
    else
        echo "WARNING: Please install espeak-ng manually"
    fi
else
    echo "[1/3] espeak-ng already installed."
fi

# 2. Python venv + packages
echo "[2/3] Setting up Python venv..."
if [ ! -d .venv ]; then
    python -m venv .venv
fi
source .venv/bin/activate
pip install --quiet piper-tts pymupdf pygame
echo "  Python packages installed."

# 3. Download voice models
echo "[3/3] Downloading German voice models..."
mkdir -p voices
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

download_voice() {
    local name=$1 path=$2
    if [ -f "voices/${name}.onnx" ] && [ -f "voices/${name}.onnx.json" ]; then
        echo "  $name: already downloaded"
        return
    fi
    echo "  $name: downloading..."
    wget -q --show-progress -O "voices/${name}.onnx" "${BASE}/${path}.onnx"
    wget -q -O "voices/${name}.onnx.json" "${BASE}/${path}.onnx.json"
}

download_voice "mike"  "de/de_DE/thorsten/high/de_DE-thorsten-high"
download_voice "nico"  "de/de_DE/thorsten_emotional/medium/de_DE-thorsten_emotional-medium"
download_voice "luca"  "de/de_DE/karlsson/low/de_DE-karlsson-low"
download_voice "jarno" "de/de_DE/pavoque/low/de_DE-pavoque-low"

echo
echo "============================================"
echo "  Setup complete!"
echo ""
echo "  Run the presentation:"
echo "    source .venv/bin/activate"
echo "    python present.py"
echo "============================================"
