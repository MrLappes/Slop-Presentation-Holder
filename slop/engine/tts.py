"""Text-to-speech engine using Piper TTS with caching."""

import hashlib
import tempfile
import wave
from pathlib import Path

from piper import PiperVoice, SynthesisConfig


class TTSEngine:
    """Generates speech audio from text using Piper TTS voice models."""

    def __init__(self, voices_dir: Path):
        self._voices_dir = voices_dir
        self._loaded_voices: dict[str, PiperVoice] = {}

    def _get_voice(self, model_path: str | Path) -> PiperVoice:
        """Load a voice model, or return it from cache if already loaded."""
        key = str(model_path)
        if key not in self._loaded_voices:
            print(f"  Loading voice model: {model_path}...", end=" ", flush=True)
            self._loaded_voices[key] = PiperVoice.load(key)
            print("OK")
        return self._loaded_voices[key]

    @staticmethod
    def _params_hash(text: str, tts_params: dict) -> str:
        """Compute an MD5 hash of text + synthesis parameters for cache keys."""
        content = text + str(sorted(tts_params.items()))
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _synthesis_config(tts_params: dict) -> SynthesisConfig:
        """Convert app TTS settings to Piper's synthesis config."""
        return SynthesisConfig(
            speaker_id=tts_params.get("speaker_id"),
            length_scale=tts_params.get("length_scale", 1.0),
            noise_scale=tts_params.get("noise_scale", 0.667),
            noise_w_scale=tts_params.get("noise_w_scale", 0.8),
        )

    def _synthesize_to_wav(self, text: str, voice: PiperVoice,
                           tts_params: dict, out_path: Path) -> None:
        """Run Piper synthesis and write the result to a WAV file."""
        syn_config = self._synthesis_config(tts_params)
        with wave.open(str(out_path), "wb") as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=syn_config)

    def generate_slide(self, slide_idx: int, text: str,
                       voice_model_path, tts_params: dict,
                       cache_dir: Path, force: bool = False) -> Path:
        """Generate audio for a single slide."""
        cache_dir.mkdir(parents=True, exist_ok=True)

        h = self._params_hash(text, tts_params)
        out_path = cache_dir / f"slide_{slide_idx:02d}_{h[:8]}.wav"

        if not force and out_path.exists() and out_path.stat().st_size > 0:
            return out_path

        if out_path.exists():
            out_path.unlink()

        voice = self._get_voice(voice_model_path)
        self._synthesize_to_wav(text, voice, tts_params, out_path)
        return out_path

    def generate_all(self, slides: list[dict], presenters: dict,
                     cache_dir: Path,
                     progress_callback=None) -> list[Path]:
        """Generate audio for all slides."""
        cache_dir.mkdir(parents=True, exist_ok=True)
        total = len(slides)
        paths = []

        for i, slide in enumerate(slides):
            name = slide["presenter"]
            cfg = presenters[name]

            tts_params = {
                "length_scale": cfg.get("length_scale", 1.0),
                "noise_scale": cfg.get("noise_scale", 0.667),
                "noise_w_scale": cfg.get("noise_w_scale", 0.8),
            }
            if "speaker_id" in cfg:
                tts_params["speaker_id"] = cfg["speaker_id"]

            h = self._params_hash(slide["text"], tts_params)
            out_path = cache_dir / f"slide_{i:02d}_{h[:8]}.wav"

            if out_path.exists() and out_path.stat().st_size > 0:
                print(f"  [{i + 1}/{total}] cached: {name}")
                paths.append(out_path)
            else:
                if out_path.exists():
                    out_path.unlink()
                print(f"  [{i + 1}/{total}] generating: {name} - Slide {i + 1}...",
                      flush=True)
                voice = self._get_voice(cfg["voice_model"])
                self._synthesize_to_wav(slide["text"], voice, tts_params, out_path)
                paths.append(out_path)

            if progress_callback:
                progress_callback(i + 1, total)

        print("  All audio ready.\n")
        return paths

    def preview_text(self, text: str, voice_model_path,
                     tts_params: dict) -> Path:
        """Generate speech for preview and return path to a temporary WAV file."""
        voice = self._get_voice(voice_model_path)

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()

        self._synthesize_to_wav(text, voice, tts_params, tmp_path)
        return tmp_path
