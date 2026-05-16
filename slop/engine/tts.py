"""Text-to-speech engine using Piper TTS with caching."""

import hashlib
import os
import tempfile
import sys
import wave
from pathlib import Path

from piper.voice import PiperVoice
from piper.config import SynthesisConfig


_ESPEAK_DATA_PATCHED = False


def _resolve_espeak_data_path() -> Path:
    """Find an espeak-ng data directory that exists in the current runtime."""
    env_candidates = (
        os.environ.get("PIPER_ESPEAK_DATA_PATH"),
        os.environ.get("ESPEAK_DATA_PATH"),
        os.environ.get("ESPEAK_DATA_DIR"),
    )
    for raw_path in env_candidates:
        if raw_path:
            candidate = Path(raw_path).expanduser()
            if candidate.exists():
                return candidate

    try:
        import piper_phonemize

        package_dir = Path(piper_phonemize.__file__).resolve().parent
        candidate = package_dir / "espeak-ng-data"
        if candidate.exists():
            return candidate
    except Exception:
        pass

    bundle_candidates = []
    frozen_dir = Path(getattr(sys, "_MEIPASS", "")) if hasattr(sys, "_MEIPASS") else None
    if frozen_dir:
        bundle_candidates.append(frozen_dir / "piper_phonemize" / "espeak-ng-data")
        bundle_candidates.append(frozen_dir / "espeak-ng-data")

    bundle_candidates.extend([
        Path("/usr/lib/x86_64-linux-gnu/espeak-ng-data"),
        Path("/usr/share/espeak-ng-data"),
        Path("/usr/local/share/espeak-ng-data"),
        Path("/usr/share/espeak-data"),
    ])

    for candidate in bundle_candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Could not find an espeak-ng data directory. Set PIPER_ESPEAK_DATA_PATH to a valid path."
    )


def _patch_piper_espeak_phonemizer() -> None:
    """Force piper's phonemizer to use an existing espeak-ng data directory."""
    global _ESPEAK_DATA_PATCHED
    if _ESPEAK_DATA_PATCHED:
        return

    from piper import voice as piper_voice_module
    from piper_phonemize import phonemize_espeak as base_phonemize_espeak

    data_path = _resolve_espeak_data_path()

    def phonemize_espeak_with_data_path(text: str, voice: str, data_path_override=None):
        return base_phonemize_espeak(text, voice, data_path_override or data_path)

    piper_voice_module.phonemize_espeak = phonemize_espeak_with_data_path
    _ESPEAK_DATA_PATCHED = True


class TTSEngine:
    """Generates speech audio from text using Piper TTS voice models.

    Voice models are lazy-loaded and cached by path for reuse across calls.
    """

    def __init__(self, voices_dir: Path):
        self._voices_dir = voices_dir
        self._loaded_voices: dict[str, PiperVoice] = {}
        _patch_piper_espeak_phonemizer()

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

    def _synthesize_to_wav(self, text: str, voice: PiperVoice,
                           tts_params: dict, out_path: Path) -> None:
        """Run Piper synthesis and write the result to a WAV file."""
        syn_config = SynthesisConfig(
            length_scale=tts_params.get("length_scale", 1.0),
            noise_scale=tts_params.get("noise_scale", 0.667),
            noise_w_scale=tts_params.get("noise_w_scale", 0.8),
        )

        speaker_id = tts_params.get("speaker_id")
        synth_kwargs = {}
        if speaker_id is not None:
            synth_kwargs["speaker_id"] = speaker_id

        audio_bytes = b""
        try:
            for chunk in voice.synthesize(text, syn_config, **synth_kwargs):
                audio_bytes += chunk.audio_int16_bytes
        except TypeError:
            # Backward-compat for older piper-tts versions without speaker_id arg.
            for chunk in voice.synthesize(text, syn_config):
                audio_bytes += chunk.audio_int16_bytes

        sample_rate = voice.config.sample_rate
        channels = 1
        sample_width = 2

        with wave.open(str(out_path), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_bytes)

    def generate_slide(self, slide_idx: int, text: str,
                       voice_model_path, tts_params: dict,
                       cache_dir: Path, force: bool = False) -> Path:
        """Generate audio for a single slide.

        Args:
            slide_idx: Slide index (used in filename).
            text: The narration text to synthesize.
            voice_model_path: Path to the Piper .onnx voice model.
            tts_params: Dict with length_scale, noise_scale, noise_w_scale,
                and optionally speaker_id.
            cache_dir: Directory to store cached WAV files.
            force: If True, regenerate even if cached file exists.

        Returns:
            Path to the generated WAV file.
        """
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
        """Generate audio for all slides.

        Args:
            slides: List of dicts with "presenter" and "text" keys.
            presenters: Dict of {name: {"model": path, "length_scale": ..., ...}}.
            cache_dir: Directory to store cached WAV files.
            progress_callback: Optional callable(current, total) for progress.

        Returns:
            List of Paths to generated WAV files, one per slide.
        """
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
                print(f"  [{i + 1}/{total}] generating: {name} — Slide {i + 1}...",
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
        """Generate speech for preview and return path to a temporary WAV file.

        The caller is responsible for cleaning up the temp file when done.
        """
        voice = self._get_voice(voice_model_path)

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()

        self._synthesize_to_wav(text, voice, tts_params, tmp_path)
        return tmp_path
