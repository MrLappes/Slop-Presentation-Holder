# Slop Presentation Holder

Auto-presenting PDF slide deck with multi-personality TTS narration, animated speaker avatar, and a full desktop GUI for creating and managing presentations.

## Desktop App Builds (Recommended)

This repo now includes native desktop packaging for Linux, macOS, and Windows.

- Workflow: `.github/workflows/build-desktop-apps.yml`
- PyInstaller spec: `slop.spec`
- Build scripts:
  - `scripts/build-linux.sh`
  - `scripts/build-macos.sh`
  - `scripts/build-windows.ps1`

Run local builds:

```bash
# Linux
bash scripts/build-linux.sh

# macOS
bash scripts/build-macos.sh
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts/build-windows.ps1
```

Artifacts are created under `dist/SlopPresentationHolder`.

To build all OS artifacts automatically, run the GitHub Actions workflow "Build Desktop Apps" (manual trigger) or push a tag like `v1.0.0`.

## Quick Start (Docker)

Use the base compose file plus your OS override file.

### Linux (X11)

```bash
# allow local Docker containers to open windows on your desktop
xhost +local:docker

# optional but recommended for reliable UID/GID mapping
export UID=$(id -u)
export GID=$(id -g)

# run app (PyQt window opens on your host, audio plays via host PulseAudio)
docker compose -f docker-compose.yml -f docker-compose.linux-x11.yml up --build
```

When done, remove the relaxed X11 rule:

```bash
xhost -local:docker
```

### Linux (Wayland)

```bash
xhost +local:docker
export UID=$(id -u)
export GID=$(id -g)

docker compose -f docker-compose.yml -f docker-compose.linux-wayland.yml up --build
```

If your Qt build does not expose native Wayland in your distro setup, it falls back to XWayland automatically.

### macOS

```bash
# 1) install and run XQuartz, then enable "Allow connections from network clients"
# 2) in an XQuartz terminal: xhost + 127.0.0.1

docker compose -f docker-compose.yml -f docker-compose.mac.yml up --build
```

For host audio on macOS, run a PulseAudio server on the host and expose TCP port 4713, then set `PULSE_SERVER` if needed.

### Windows (Docker Desktop)

```bash
# 1) run an X server (VcXsrv or Xming)
# 2) allow access from Docker Desktop / WSL network

docker compose -f docker-compose.yml -f docker-compose.windows.yml up --build
```

For host audio on Windows, run a PulseAudio server and expose TCP port 4713.

All project files are mounted into the container, so PDFs/JSON files in this repo are directly available in the app.

### Stop

```bash
docker compose down
```

## Quick Start (Native)

```bash
# 1. Run setup (installs deps + downloads 4 German voice models ~300MB)
bash setup.sh

# 2. Activate venv
source .venv/bin/activate

# 3. Launch the GUI app
python slop.py
```

## GUI Features

### Script Editor
- Visual slide list with PDF thumbnails
- Per-slide presenter assignment and narration text editor
- Preview and regenerate audio per slide

### Presenter Manager
- Create, edit, and delete presenters
- Voice model selection with speed/expression/duration sliders
- Multi-speaker model support (e.g. emotional voices with moods)
- Color picker and avatar GIF tinting preview

### Voice Library
- Browse all available Piper TTS voices from HuggingFace
- Filter by language, quality, and search by name
- One-click download with progress tracking

### Export Prompt Template
- Extracts text from each PDF slide
- Generates a ready-to-use prompt file for ChatGPT, Claude, or any LLM
- Paste the AI-generated narration scripts back into the Script Editor

### Export MP4
- Renders the full presentation to a video file (1920x1080, 30 FPS)
- Includes slide transitions, GIF animation, presenter badges, and synced audio

## Presentation Controls

| Key | Action |
|---|---|
| `SPACE` / `->` / Click | Next slide |
| `<-` | Previous slide |
| `R` | Replay current slide audio |
| `S` | Skip / stop audio |
| `F` | Toggle fullscreen |
| `Q` / `ESC` | Quit |

## Creating a New Presentation

1. **New Project**: Click "New" in the toolbar, select a PDF
2. **Add Presenters**: Go to the Presenters tab, click "+ Add", configure voice and color
3. **Write Scripts**: Use the Script Editor tab to assign presenters and write narration per slide
4. **AI Assist**: Click "Export Prompt" to generate a prompt file, paste into your preferred AI, copy scripts back
5. **Generate Audio**: Click "Generate Audio" to synthesize all narration
6. **Present**: Click the green "Present" button for fullscreen presentation
7. **Export**: Click "Export MP4" to render a shareable video
8. **Save**: Save your project as a .json file for later

## Project Format

Projects are saved as `.json` files containing presenters, slides, voice settings, and GIF configuration. The included `templates/agentic_shield.json` demonstrates the format with a full 14-slide example.

## Project Structure

```
slop.py                            # GUI app entry point
requirements.txt                   # Python dependencies
setup.sh                           # Native setup script
Dockerfile                         # Docker image build
docker-compose.yml                 # Docker one-command run
docker-entrypoint.sh               # Container startup
Agentic_Shield_Zero_Trust.pdf      # Example slide deck
morshu-zelda.gif                   # Speaker avatar (animated)

slop/
  app.py                           # QApplication bootstrap
  project.py                       # Project data model + save/load
  constants.py                     # Paths, URLs
  gui/
    main_window.py                 # Main window + toolbar
    script_editor.py               # Slide list + narration editor
    presenter_manager.py           # Presenter CRUD
    voice_browser.py               # Voice model download UI
    widgets.py                     # Color picker, sliders, GIF preview
  engine/
    presentation.py                # Fullscreen pygame runner
    video_export.py                # MP4 export via ffmpeg
    tts.py                         # Piper TTS wrapper
    pdf_renderer.py                # PDF rendering + text extraction
    gif_loader.py                  # GIF frame loading + tinting
    audio_player.py                # System audio playback
  voices/
    model_registry.py              # Voice model catalog + download

templates/
  agentic_shield.json              # Example presentation project
  prompt_template.md               # AI prompt template for scripts

voices/                            # TTS models (downloaded by setup.sh)
audio_cache/                       # Generated audio (auto-created)
projects/                          # User project files (Docker volume)
```

## Requirements (Native)

- Python 3.10+
- espeak-ng
- ffmpeg for MP4 export
- Audio player: pw-play, paplay, aplay, or ffplay

## Requirements (Docker)

- Docker with Docker Compose
- Linux X11 or Wayland session, or an X server on macOS/Windows
- For live audio preview from container: PulseAudio/PipeWire available on host
- On Linux native audio path: Pulse socket at `$XDG_RUNTIME_DIR/pulse/native`
