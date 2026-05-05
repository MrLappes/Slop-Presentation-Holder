# Agentic Shield — Automated Presentation System

Auto-presenting PDF slide deck with multi-personality German TTS narration and animated speaker avatar.

## Quick Start

```bash
# 1. Run setup (installs deps + downloads 4 German voice models ~300MB)
bash setup.sh

# 2. Activate venv
source .venv/bin/activate

# 3. Run presentation
python present.py
```

## Controls

| Key | Action |
|---|---|
| `SPACE` / `→` / Click | Next slide |
| `←` | Previous slide |
| `R` | Replay current slide audio |
| `S` | Skip / stop audio |
| `F` | Toggle fullscreen |
| `Q` / `ESC` | Quit |

## Creating a New Presentation

### 1. Replace the PDF

Drop your new PDF into the project root and update `PDF_PATH` in `present.py`:

```python
PDF_PATH = SCRIPT_DIR / "Your_New_Presentation.pdf"
```

### 2. Write Narration for Each Slide

Edit the `SLIDES` list in `present.py`. Each entry is a dict with a presenter name and German text:

```python
SLIDES = [
    {
        "presenter": "Mike",
        "text": "Your German narration for slide 1...",
    },
    {
        "presenter": "Nico",
        "text": "Your German narration for slide 2...",
    },
    # ... one entry per slide
]
```

The number of entries in `SLIDES` must match the number of pages in your PDF.

### 3. Assign Presenters

Four presenters rotate with distinct voices and personalities:

| Name | Voice Model | Personality | Color |
|---|---|---|---|
| **Mike** | thorsten-high | Professional, dry humor | Blue |
| **Nico** | thorsten-emotional | Hyperactive, excited | Red |
| **Luca** | karlsson | Casual, chill | Green |
| **Jarno** | pavoque | Dramatic, theatrical | Purple |

Assign any presenter to any slide by setting `"presenter"` in the slide dict.

### 4. Customize Presenters

Edit the `PRESENTERS` dict in `present.py` to change voice parameters:

```python
"Mike": {
    "model": VOICES_DIR / "mike.onnx",
    "length_scale": 1.0,      # Speed: <1 = faster, >1 = slower
    "noise_scale": 0.667,     # Expressiveness: higher = more variation
    "noise_w_scale": 0.8,     # Phoneme duration variation
    "color": (41, 128, 185),  # Badge + GIF tint color (RGB)
    "title": "Der Ernste",    # Subtitle on badge
},
```

### 5. Regenerate Audio

Delete the `audio_cache/` folder and run `present.py` again. Audio is regenerated on first run and cached for subsequent runs.

```bash
rm -rf audio_cache/
python present.py
```

### 6. Change the Speaker Avatar

Replace `morshu-zelda.gif` with any animated GIF. The script tints pixels matching `#eb4e0a` with each presenter's color and removes the black background.

To change the target color, edit `TARGET_R, TARGET_G, TARGET_B` and `TOLERANCE` in the `load_speaker_frames()` function.

## Project Structure

```
├── present.py                  # Main presentation script
├── setup.sh                    # One-command setup
├── morshu-zelda.gif            # Speaker avatar (animated)
├── Agentic_Shield_Zero_Trust.pdf  # Slide deck
├── PRESENTATION.md             # Detailed reference document
├── SPEAKER_DECK.md             # 8-min speaker notes deck
├── SOURCES.txt                 # All reference URLs
├── voices/                     # TTS models (downloaded by setup.sh)
└── audio_cache/                # Generated audio (auto-created)
```

## Requirements

- Python 3.10+
- espeak-ng (`sudo pacman -S espeak-ng`)
- Audio player: pw-play, paplay, aplay, or ffplay
