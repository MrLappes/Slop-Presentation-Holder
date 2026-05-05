"""Audio playback using system audio players."""

import os
import shutil
import subprocess
from pathlib import Path


class AudioPlayer:
    """Wraps system audio player (pw-play, paplay, aplay, or ffplay)."""

    def __init__(self):
        self._player = self._find_player()
        self._proc = None

    @staticmethod
    def _find_player():
        for cmd in ("pw-play", "paplay", "aplay", "ffplay"):
            if shutil.which(cmd):
                return cmd
        return None

    def play(self, path: Path) -> None:
        """Stop any current playback and start playing the given audio file."""
        self.stop()

        audio_path = str(path)
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            return

        if not self._player:
            print("  No audio player found (tried pw-play, paplay, aplay, ffplay)")
            return

        try:
            if self._player == "ffplay":
                cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", audio_path]
            else:
                cmd = [self._player, audio_path]
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"  Audio error {path}: {e}")

    def stop(self) -> None:
        """Terminate current playback if active."""
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    def is_playing(self) -> bool:
        """Return True if audio is currently playing."""
        return self._proc is not None and self._proc.poll() is None
