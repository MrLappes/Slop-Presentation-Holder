FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    QT_QPA_PLATFORM=xcb \
    SDL_AUDIODRIVER=dummy \
    PYTHONDONTWRITEBYTECODE=1

# System deps: espeak-ng, ffmpeg, X11/VNC/noVNC, fonts, audio tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    ffmpeg \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    openbox \
    wget \
    curl \
    fonts-dejavu-core \
    libgl1 \
    libegl1 \
    libxkbcommon0 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-keysyms1 \
    libxcb-shape0 \
    libdbus-1-3 \
    pulseaudio-utils \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download voice models at build time
RUN mkdir -p voices && \
    BASE="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0" && \
    curl -sfL --retry 5 --retry-delay 3 -o voices/mike.onnx "$BASE/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx" && \
    curl -sfL --retry 5 --retry-delay 3 -o voices/mike.onnx.json "$BASE/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx.json" && \
    curl -sfL --retry 5 --retry-delay 3 -o voices/nico.onnx "$BASE/de/de_DE/thorsten_emotional/medium/de_DE-thorsten_emotional-medium.onnx" && \
    curl -sfL --retry 5 --retry-delay 3 -o voices/nico.onnx.json "$BASE/de/de_DE/thorsten_emotional/medium/de_DE-thorsten_emotional-medium.onnx.json" && \
    curl -sfL --retry 5 --retry-delay 3 -o voices/luca.onnx "$BASE/de/de_DE/karlsson/low/de_DE-karlsson-low.onnx" && \
    curl -sfL --retry 5 --retry-delay 3 -o voices/luca.onnx.json "$BASE/de/de_DE/karlsson/low/de_DE-karlsson-low.onnx.json" && \
    curl -sfL --retry 5 --retry-delay 3 -o voices/jarno.onnx "$BASE/de/de_DE/pavoque/low/de_DE-pavoque-low.onnx" && \
    curl -sfL --retry 5 --retry-delay 3 -o voices/jarno.onnx.json "$BASE/de/de_DE/pavoque/low/de_DE-pavoque-low.onnx.json"

# Copy application
COPY slop.py .
COPY slop/ slop/
COPY templates/ templates/
COPY morshu-zelda.gif .
COPY Agentic_Shield_Zero_Trust.pdf .
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Audio cache + projects volume
RUN mkdir -p audio_cache projects

EXPOSE 6080

ENTRYPOINT ["./docker-entrypoint.sh"]
