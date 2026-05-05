"""MP4 video export: renders presentation frames and pipes to ffmpeg."""

import os
import subprocess
import tempfile
import wave
from pathlib import Path

import pygame

from slop.engine.pdf_renderer import load_slides_as_surfaces
from slop.engine.gif_loader import load_speaker_frames
from slop.engine.presentation import (
    render_frame_to_surface, render_fade_frame, audio_path_for_slide,
)

FADE_DURATION_MS = 350
GIF_INTERVAL_S = 0.1


def get_wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def _get_wav_params(path: Path) -> tuple:
    with wave.open(str(path), "rb") as wf:
        return wf.getnchannels(), wf.getsampwidth(), wf.getframerate()


def build_combined_audio(
    slide_audio_paths: list,
    auto_advance_delay: float,
    fade_duration: float,
    output_path: Path,
) -> None:
    """Concatenate slide WAVs with silence gaps into a single WAV."""
    channels, sampwidth, framerate = 1, 2, 22050
    for p in slide_audio_paths:
        if p:
            channels, sampwidth, framerate = _get_wav_params(p)
            break

    silence_duration = auto_advance_delay + fade_duration
    silence_frames = int(silence_duration * framerate)
    silence_bytes = b"\x00" * (silence_frames * channels * sampwidth)

    with wave.open(str(output_path), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(sampwidth)
        out.setframerate(framerate)

        for i, audio_path in enumerate(slide_audio_paths):
            if audio_path:
                with wave.open(str(audio_path), "rb") as wf:
                    out.writeframes(wf.readframes(wf.getnframes()))
            else:
                fallback = int(3.0 * framerate)
                out.writeframes(b"\x00" * (fallback * channels * sampwidth))

            is_last = i == len(slide_audio_paths) - 1
            if not is_last:
                out.writeframes(silence_bytes)


def export_mp4(
    project_data: dict,
    output_path: Path,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    progress_callback=None,
    abort_flag=None,
) -> None:
    """Render the full presentation to an MP4 file via ffmpeg.

    Args:
        project_data: Engine dict from SlopProject.to_engine_dict().
        output_path: Destination .mp4 file path.
        width: Video width in pixels.
        height: Video height in pixels.
        fps: Frames per second.
        progress_callback: Optional callable(current_frame, total_frames, message).
        abort_flag: Optional callable returning True to abort export.
    """
    import time

    pdf_path = Path(project_data["pdf_path"])
    slides = project_data["slides"]
    presenters = project_data["presenters"]
    gif_cfg = project_data.get("gif", {})
    auto_advance_delay = project_data.get("auto_advance_delay", 1.2)
    cache_dir = Path(project_data.get("cache_dir", "audio_cache"))

    num_slides = len(slides)
    fade_duration = FADE_DURATION_MS / 1000.0
    transition_frames = round(fade_duration * fps)
    gif_interval_frames = max(1, round(GIF_INTERVAL_S * fps))

    # Init pygame headless
    old_driver = os.environ.get("SDL_VIDEODRIVER")
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    screen = pygame.Surface((width, height))

    try:
        font_big = pygame.font.SysFont("DejaVu Sans,Arial,Helvetica", 28, bold=True)
        font_small = pygame.font.SysFont("DejaVu Sans,Arial,Helvetica", 20)
        font_hint = pygame.font.SysFont("DejaVu Sans,Arial,Helvetica", 16)
    except Exception:
        font_big = pygame.font.Font(None, 32)
        font_small = pygame.font.Font(None, 24)
        font_hint = pygame.font.Font(None, 18)

    if progress_callback:
        progress_callback(0, 0, "Loading slides and assets...")

    slide_surfaces = load_slides_as_surfaces(pdf_path, width, height)

    gif_path = gif_cfg.get("path", "")
    speaker_frames = load_speaker_frames(
        gif_path, presenters,
        target_color=tuple(gif_cfg.get("target_color", [235, 78, 10])),
        tolerance=gif_cfg.get("tolerance", 60),
        scale=gif_cfg.get("scale", 2.0),
    )

    # Compute per-slide timing
    slide_audio_paths = []
    slide_timings = []
    for i in range(num_slides):
        audio_p = audio_path_for_slide(cache_dir, i)
        slide_audio_paths.append(audio_p)

        if audio_p:
            audio_dur = get_wav_duration(audio_p)
        else:
            audio_dur = 3.0

        audio_frames = round(audio_dur * fps)
        is_last = i == num_slides - 1
        delay_frames = 0 if is_last else round(auto_advance_delay * fps)

        slide_timings.append({
            "audio_frames": audio_frames,
            "delay_frames": delay_frames,
        })

    # Precompute total frame count for accurate progress
    total_frames = 0
    for i in range(num_slides):
        if i > 0:
            total_frames += transition_frames + 1
        total_frames += slide_timings[i]["audio_frames"] + slide_timings[i]["delay_frames"]

    total_duration = total_frames / fps
    frames_written = 0
    start_time = None

    def report(msg):
        if not progress_callback:
            return
        progress_callback(frames_written, total_frames, msg)

    # Build combined audio
    tmp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_audio_path = Path(tmp_audio.name)
    tmp_audio.close()

    try:
        report(f"Building audio track ({num_slides} slides)...")

        build_combined_audio(
            slide_audio_paths, auto_advance_delay, fade_duration, tmp_audio_path,
        )

        # Start ffmpeg
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-pixel_format", "rgb24",
            "-video_size", f"{width}x{height}",
            "-framerate", str(fps),
            "-i", "pipe:0",
            "-i", str(tmp_audio_path),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(output_path),
        ]

        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        start_time = time.monotonic()

        def pipe_frame():
            nonlocal frames_written
            raw = pygame.image.tobytes(screen, "RGB")
            ffmpeg_proc.stdin.write(raw)
            frames_written += 1

        def check_abort():
            if abort_flag and abort_flag():
                ffmpeg_proc.kill()
                raise InterruptedError("Export cancelled")

        def eta_str():
            if not start_time or frames_written < fps:
                return ""
            elapsed = time.monotonic() - start_time
            rate = frames_written / elapsed
            remaining = (total_frames - frames_written) / rate
            m, s = divmod(int(remaining), 60)
            return f" · ~{m}:{s:02d} left" if m else f" · ~{s}s left"

        # Render frames
        for slide_idx in range(num_slides):
            check_abort()

            # Fade transition (not for first slide)
            if slide_idx > 0:
                report(f"Slide {slide_idx + 1}/{num_slides} — Transition{eta_str()}")
                old_surf = slide_surfaces[slide_idx - 1].copy()
                new_surf = slide_surfaces[slide_idx].copy()
                sw, sh = screen.get_width(), screen.get_height()
                nx = (sw - new_surf.get_width()) // 2
                ny = (sh - new_surf.get_height()) // 2
                img_rect = (nx, ny)

                for step in range(transition_frames + 1):
                    check_abort()
                    alpha = int(255 * step / max(1, transition_frames))
                    render_fade_frame(screen, old_surf, new_surf, img_rect, alpha)
                    pipe_frame()

            # Slide content frames
            audio_fc = slide_timings[slide_idx]["audio_frames"]
            delay_fc = slide_timings[slide_idx]["delay_frames"]
            total_slide_frames = audio_fc + delay_fc
            slide_dur = total_slide_frames / fps

            report(f"Slide {slide_idx + 1}/{num_slides} — Rendering ({slide_dur:.1f}s){eta_str()}")

            gif_frame_idx = 0
            update_interval = max(1, fps)
            for frame_num in range(total_slide_frames):
                check_abort()
                is_audio_phase = frame_num < audio_fc
                if is_audio_phase:
                    gif_frame_idx = frame_num // gif_interval_frames

                render_frame_to_surface(
                    screen, slide_surfaces, slides, presenters,
                    slide_idx, num_slides, speaker_frames,
                    gif_frame_idx,
                    font_big, font_small, font_hint,
                    show_controls=False,
                )
                pipe_frame()

                if frame_num % update_interval == 0:
                    phase = "Speaking" if is_audio_phase else "Pause"
                    report(f"Slide {slide_idx + 1}/{num_slides} — {phase}{eta_str()}")

        # Finalize
        report("Finalizing video...")
        ffmpeg_proc.stdin.close()
        _, stderr = ffmpeg_proc.communicate(timeout=120)

        if ffmpeg_proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")[-500:]
            raise RuntimeError(f"ffmpeg failed (code {ffmpeg_proc.returncode}):\n{err_msg}")

        elapsed = time.monotonic() - start_time
        m, s = divmod(int(elapsed), 60)
        report(f"Done — {total_duration:.0f}s video in {m}:{s:02d}")

    except InterruptedError:
        if output_path.exists():
            output_path.unlink()
        raise
    finally:
        pygame.quit()
        if old_driver is not None:
            os.environ["SDL_VIDEODRIVER"] = old_driver
        else:
            os.environ.pop("SDL_VIDEODRIVER", None)
        if tmp_audio_path.exists():
            tmp_audio_path.unlink()
