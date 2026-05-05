from pathlib import Path

APP_DIR = Path(__file__).parent.parent
VOICES_DIR = APP_DIR / "voices"
CACHE_DIR = APP_DIR / "audio_cache"
TEMPLATES_DIR = APP_DIR / "templates"

HF_BASE_URL = "https://huggingface.co/rhasspy/piper-voices"
HF_VOICES_JSON = f"{HF_BASE_URL}/raw/main/voices.json"
HF_MODEL_BASE = f"{HF_BASE_URL}/resolve/v1.0.0"
