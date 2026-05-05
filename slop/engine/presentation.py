"""Pygame-based fullscreen presentation engine.

Handles slide rendering, fade transitions, GIF animation,
audio playback, auto-advance, and keyboard/mouse controls.
"""

import time
from pathlib import Path

import pygame

from slop.engine.audio_player import AudioPlayer
from slop.engine.pdf_renderer import load_slides_as_surfaces
from slop.engine.gif_loader import load_speaker_frames


# ── Drawing helpers ──────────────────────────────────────────────


def draw_presenter_badge(screen, presenter_name, presenter_cfg,
                         slide_idx, total, font_big, font_small):
    """Draw the presenter name badge and slide progress indicator."""
    badge_text = f"{presenter_name} — {presenter_cfg['title']}"
    progress_text = f"{slide_idx + 1} / {total}"

    badge_surf = font_big.render(badge_text, True, (255, 255, 255))
    progress_surf = font_small.render(progress_text, True, (200, 200, 200))

    pad_x, pad_y = 20, 10
    badge_w = badge_surf.get_width() + pad_x * 2
    badge_h = badge_surf.get_height() + pad_y * 2

    badge_bg = pygame.Surface((badge_w, badge_h), pygame.SRCALPHA)
    r, g, b = presenter_cfg["color"]
    pygame.draw.rect(badge_bg, (r, g, b, 220), (0, 0, badge_w, badge_h),
                     border_radius=12)
    badge_bg.blit(badge_surf, (pad_x, pad_y))

    screen_w = screen.get_width()
    screen_h = screen.get_height()

    screen.blit(badge_bg, (20, screen_h - badge_h - 20))

    prog_x = screen_w - progress_surf.get_width() - 30
    prog_y = screen_h - progress_surf.get_height() - 28
    prog_bg = pygame.Surface(
        (progress_surf.get_width() + 20, progress_surf.get_height() + 12),
        pygame.SRCALPHA,
    )
    pygame.draw.rect(
        prog_bg, (0, 0, 0, 160),
        (0, 0, prog_bg.get_width(), prog_bg.get_height()),
        border_radius=8,
    )
    screen.blit(prog_bg, (prog_x - 10, prog_y - 6))
    screen.blit(progress_surf, (prog_x, prog_y))


def draw_controls_hint(screen, font):
    """Draw the keyboard controls hint bar at the top of the screen."""
    hints = "SPACE/→ next  |  ← back  |  R replay  |  S skip  |  Q quit  |  F fullscreen"
    hint_surf = font.render(hints, True, (150, 150, 150))
    x = (screen.get_width() - hint_surf.get_width()) // 2
    y = 8
    bg = pygame.Surface((hint_surf.get_width() + 16, hint_surf.get_height() + 8),
                        pygame.SRCALPHA)
    pygame.draw.rect(bg, (0, 0, 0, 100),
                     (0, 0, bg.get_width(), bg.get_height()), border_radius=6)
    screen.blit(bg, (x - 8, y - 4))
    screen.blit(hint_surf, (x, y))


def render_fade_frame(surface, old_surf, new_surf, slide_img_rect, alpha):
    """Render a single crossfade frame at the given alpha (0-255) onto surface."""
    surface.fill((0, 0, 0))
    if old_surf:
        old_surf.set_alpha(255 - alpha)
        surface.blit(old_surf, slide_img_rect)
    new_surf.set_alpha(alpha)
    surface.blit(new_surf, slide_img_rect)


def fade_transition(screen, old_surf, new_surf, slide_img_rect, duration_ms=400):
    """Crossfade between two slide surfaces.

    Returns False if a QUIT event is received during the transition.
    """
    clock = pygame.time.Clock()
    steps = max(1, duration_ms // 16)
    for step in range(steps + 1):
        alpha = int(255 * step / steps)
        render_fade_frame(screen, old_surf, new_surf, slide_img_rect, alpha)
        pygame.display.flip()
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
    new_surf.set_alpha(255)
    return True


# ── Frame rendering ──────────────────────────────────────────────


def render_frame_to_surface(surface, slide_surfaces, slides, presenters, current,
                            num_slides, speaker_frames_dict, gif_frame_idx,
                            font_big, font_small, font_hint, show_controls):
    """Render a single presentation frame onto the given surface (no display flip)."""
    surf = slide_surfaces[current]
    sw, sh = surface.get_width(), surface.get_height()
    img_x = (sw - surf.get_width()) // 2
    img_y = (sh - surf.get_height()) // 2

    surface.fill((0, 0, 0))
    surface.blit(surf, (img_x, img_y))

    presenter_name = slides[current]["presenter"]
    presenter_cfg = presenters[presenter_name]
    draw_presenter_badge(surface, presenter_name, presenter_cfg,
                         current, num_slides, font_big, font_small)

    if speaker_frames_dict and presenter_name in speaker_frames_dict:
        frames = speaker_frames_dict[presenter_name]
        if frames:
            frame_surf = frames[gif_frame_idx % len(frames)]
            gx = sw - frame_surf.get_width() - 30
            gy = sh - frame_surf.get_height() - 20
            surface.blit(frame_surf, (gx, gy))

    if show_controls:
        draw_controls_hint(surface, font_hint)


def render_frame(screen, slide_surfaces, slides, presenters, current,
                 num_slides, speaker_frames_dict, gif_frame_idx,
                 font_big, font_small, font_hint, show_controls):
    """Render a single presentation frame and flip the display."""
    render_frame_to_surface(screen, slide_surfaces, slides, presenters, current,
                            num_slides, speaker_frames_dict, gif_frame_idx,
                            font_big, font_small, font_hint, show_controls)
    pygame.display.flip()


# ── Audio file lookup ────────────────────────────────────────────


def audio_path_for_slide(cache_dir: Path, idx: int):
    """Find the cached audio file for a slide index.

    Supports hashed filenames (slide_00_abcd1234.wav), legacy filenames
    (slide_00.wav), and falls back to the parent directory for backward
    compatibility with audio generated by the standalone present.py.
    """
    for p in sorted(cache_dir.glob(f"slide_{idx:02d}_*.wav")):
        if p.stat().st_size > 0:
            return p
    legacy = cache_dir / f"slide_{idx:02d}.wav"
    if legacy.exists() and legacy.stat().st_size > 0:
        return legacy
    parent = cache_dir.parent
    if parent != cache_dir:
        for p in sorted(parent.glob(f"slide_{idx:02d}_*.wav")):
            if p.stat().st_size > 0:
                return p
        legacy_parent = parent / f"slide_{idx:02d}.wav"
        if legacy_parent.exists() and legacy_parent.stat().st_size > 0:
            return legacy_parent
    return None


# ── Main presentation loop ───────────────────────────────────────


def run_presentation(project_data: dict) -> None:
    """Run the fullscreen presentation.

    Args:
        project_data: Dict containing:
            - pdf_path (str): Path to the PDF file.
            - slides (list[dict]): Each dict has "presenter" and "text" keys.
            - presenters (dict): {name: {"color": (r,g,b), "title": str, ...}}.
            - gif (dict): {"path": str, "target_color": [r,g,b],
                          "tolerance": int, "scale": float}.
            - auto_advance (bool): Whether to auto-advance after audio finishes.
            - auto_advance_delay (float): Seconds to wait after audio ends
                before advancing.
            - cache_dir (str): Path to the audio cache directory.
    """
    pdf_path = Path(project_data["pdf_path"])
    slides = project_data["slides"]
    presenters = project_data["presenters"]
    gif_cfg = project_data.get("gif", {})
    auto_advance = project_data.get("auto_advance", True)
    auto_advance_delay = project_data.get("auto_advance_delay", 1.2)
    cache_dir = Path(project_data.get("cache_dir", "audio_cache"))

    # Initialize pygame
    pygame.init()

    info = pygame.display.Info()
    screen_w, screen_h = info.current_w, info.current_h
    fullscreen = True
    screen = pygame.display.set_mode((screen_w, screen_h), pygame.FULLSCREEN)
    pygame.display.set_caption("Agentic Shield — Presentation")
    pygame.mouse.set_visible(False)

    try:
        font_big = pygame.font.SysFont("DejaVu Sans,Arial,Helvetica", 28, bold=True)
        font_small = pygame.font.SysFont("DejaVu Sans,Arial,Helvetica", 20)
        font_hint = pygame.font.SysFont("DejaVu Sans,Arial,Helvetica", 16)
    except Exception:
        font_big = pygame.font.Font(None, 32)
        font_small = pygame.font.Font(None, 24)
        font_hint = pygame.font.Font(None, 18)

    # Load assets
    print("Loading PDF slides...")
    slide_surfaces = load_slides_as_surfaces(pdf_path, screen_w, screen_h)
    num_slides = min(len(slide_surfaces), len(slides))

    print("Loading speaker GIF...")
    gif_path = gif_cfg.get("path", "")
    gif_target_color = tuple(gif_cfg.get("target_color", [235, 78, 10]))
    gif_tolerance = gif_cfg.get("tolerance", 60)
    gif_scale = gif_cfg.get("scale", 2.0)
    speaker_frames = load_speaker_frames(
        gif_path, presenters,
        target_color=gif_target_color,
        tolerance=gif_tolerance,
        scale=gif_scale,
    )

    print(f"Loaded {num_slides} slides. Starting presentation.\n")

    # Audio player
    player = AudioPlayer()

    # State
    current = 0
    prev_surface = None
    clock = pygame.time.Clock()
    need_slide_change = True
    need_transition = True
    show_controls = True
    controls_timer = time.time()
    gif_frame_idx = 0
    gif_paused_frame = 0
    last_gif_advance = time.time()
    gif_interval = 0.1
    audio_was_playing = False
    audio_done_time = None

    # ── Main loop ────────────────────────────────────────────────

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                player.stop()
                pygame.quit()
                return

            if event.type == pygame.KEYDOWN:
                show_controls = True
                controls_timer = time.time()

                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    player.stop()
                    pygame.quit()
                    return

                elif event.key in (pygame.K_SPACE, pygame.K_RIGHT):
                    player.stop()
                    audio_done_time = None
                    if current < num_slides - 1:
                        prev_surface = slide_surfaces[current].copy()
                        current += 1
                        need_slide_change = True
                        need_transition = True
                    else:
                        pygame.quit()
                        return

                elif event.key == pygame.K_LEFT:
                    player.stop()
                    audio_done_time = None
                    if current > 0:
                        prev_surface = slide_surfaces[current].copy()
                        current -= 1
                        need_slide_change = True
                        need_transition = True

                elif event.key == pygame.K_r:
                    audio_done_time = None
                    audio_file = audio_path_for_slide(cache_dir, current)
                    if audio_file:
                        player.play(audio_file)

                elif event.key == pygame.K_s:
                    player.stop()

                elif event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode(
                            (screen_w, screen_h), pygame.FULLSCREEN
                        )
                        pygame.mouse.set_visible(False)
                    else:
                        w = int(screen_w * 0.8)
                        h = int(screen_h * 0.8)
                        screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
                        pygame.mouse.set_visible(True)
                    slide_surfaces = load_slides_as_surfaces(
                        pdf_path, screen.get_width(), screen.get_height()
                    )
                    need_slide_change = True
                    need_transition = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    player.stop()
                    audio_done_time = None
                    if current < num_slides - 1:
                        prev_surface = slide_surfaces[current].copy()
                        current += 1
                        need_slide_change = True
                        need_transition = True

        if need_slide_change:
            surf = slide_surfaces[current]
            sw, sh = screen.get_width(), screen.get_height()
            img_x = (sw - surf.get_width()) // 2
            img_y = (sh - surf.get_height()) // 2
            img_rect = (img_x, img_y)

            if need_transition and prev_surface:
                fade_transition(
                    screen, prev_surface, surf.copy(), img_rect, duration_ms=350
                )

            audio_file = audio_path_for_slide(cache_dir, current)
            if audio_file:
                player.play(audio_file)
            gif_frame_idx = 0
            audio_was_playing = True
            audio_done_time = None
            need_slide_change = False
            need_transition = False
            prev_surface = None

        is_playing = player.is_playing()

        if is_playing:
            now = time.time()
            if now - last_gif_advance >= gif_interval:
                gif_frame_idx += 1
                last_gif_advance = now
            gif_paused_frame = gif_frame_idx
            audio_was_playing = True
            audio_done_time = None

        if audio_was_playing and not is_playing and audio_done_time is None:
            audio_done_time = time.time()
            audio_was_playing = False

        if show_controls and (time.time() - controls_timer > 5):
            show_controls = False

        render_frame(
            screen, slide_surfaces, slides, presenters, current, num_slides,
            speaker_frames,
            gif_paused_frame if not is_playing else gif_frame_idx,
            font_big, font_small, font_hint, show_controls,
        )

        if (auto_advance and audio_done_time
                and (time.time() - audio_done_time > auto_advance_delay)):
            if current < num_slides - 1:
                prev_surface = slide_surfaces[current].copy()
                current += 1
                need_slide_change = True
                need_transition = True
                audio_done_time = None

        clock.tick(30)
