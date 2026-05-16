#!/usr/bin/env bash
set -euo pipefail

cd /app

mkdir -p voices audio_cache projects

if [[ "${SLOP_DOWNLOAD_DEFAULT_VOICES:-1}" == "1" ]]; then
  BASE="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

  download_voice() {
    local name="$1"
    local path="$2"

    if [[ -f "voices/${name}.onnx" && -f "voices/${name}.onnx.json" ]]; then
      echo "Voice ${name} already present"
      return
    fi

    echo "Downloading voice ${name}..."
    wget -q --show-progress -O "voices/${name}.onnx" "${BASE}/${path}.onnx"
    wget -q -O "voices/${name}.onnx.json" "${BASE}/${path}.onnx.json"
  }

  download_voice "mike" "de/de_DE/thorsten/high/de_DE-thorsten-high"
  download_voice "nico" "de/de_DE/thorsten_emotional/medium/de_DE-thorsten_emotional-medium"
  download_voice "luca" "de/de_DE/karlsson/low/de_DE-karlsson-low"
  download_voice "jarno" "de/de_DE/pavoque/low/de_DE-pavoque-low"
fi

if [[ -z "${DISPLAY:-}" ]]; then
  echo "WARNING: DISPLAY is not set. GUI apps will not open."
fi

exec "$@"
