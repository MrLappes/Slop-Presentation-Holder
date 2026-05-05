# Slop Presentation Holder

Auto-presenting PDF slide deck with multi-personality TTS narration, animated speaker avatar, and a full desktop GUI for creating and managing presentations.

## Quick Start (Docker)

```bash
docker compose up --build
```

Open **http://localhost:6080** in your browser. The full GUI runs inside the container and streams to your browser via noVNC.

Drop your PDF files into the `projects/` folder to access them from the app.

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
- A web browser
