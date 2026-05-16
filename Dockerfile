FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    espeak-ng \
    ffmpeg \
    libasound2 \
    libdbus-1-3 \
    libegl1 \
    libfontconfig1 \
    libgl1 \
    libglib2.0-0 \
    libice6 \
    libnss3 \
    libsm6 \
    libx11-6 \
    libxcomposite1 \
    libxcb-cursor0 \
    libxext6 \
    libxfixes3 \
    libxkbcommon-x11-0 \
    libxrandr2 \
    libxrender1 \
    libxtst6 \
    pulseaudio-utils \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "slop.py"]
