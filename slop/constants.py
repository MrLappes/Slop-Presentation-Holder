import os
import sys
from pathlib import Path


def _bundle_dir() -> Path:
	if getattr(sys, "frozen", False):
		meipass = getattr(sys, "_MEIPASS", None)
		if meipass:
			return Path(meipass)
		return Path(sys.executable).resolve().parent
	return Path(__file__).resolve().parent.parent


def _user_data_dir() -> Path:
	if sys.platform.startswith("win"):
		base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
		if base:
			return Path(base) / "SlopPresentationHolder"
		return Path.home() / "AppData" / "Local" / "SlopPresentationHolder"

	if sys.platform == "darwin":
		return Path.home() / "Library" / "Application Support" / "SlopPresentationHolder"

	xdg_data_home = os.environ.get("XDG_DATA_HOME")
	if xdg_data_home:
		return Path(xdg_data_home) / "slop-presentation-holder"
	return Path.home() / ".local" / "share" / "slop-presentation-holder"


APP_DIR = _bundle_dir()
DATA_DIR = _user_data_dir() if getattr(sys, "frozen", False) else APP_DIR
VOICES_DIR = DATA_DIR / "voices"
CACHE_DIR = DATA_DIR / "audio_cache"
PROJECTS_DIR = DATA_DIR / "projects"
TEMPLATES_DIR = APP_DIR / "templates"

for _path in (VOICES_DIR, CACHE_DIR, PROJECTS_DIR):
	_path.mkdir(parents=True, exist_ok=True)

HF_BASE_URL = "https://huggingface.co/rhasspy/piper-voices"
HF_VOICES_JSON = f"{HF_BASE_URL}/raw/main/voices.json"
HF_MODEL_BASE = f"{HF_BASE_URL}/resolve/v1.0.0"
