"""GIF frame loading and per-presenter color tinting."""

from pathlib import Path

import pygame
from PIL import Image


def load_speaker_frames(
    gif_path,
    presenters,
    target_color=(235, 78, 10),
    tolerance=60,
    scale=2.0,
):
    """Load GIF frames, tint per presenter color, remove black background.

    Args:
        gif_path: Path to the animated GIF file.
        presenters: Dict of {name: {"color": (r, g, b), ...}}.
        target_color: The (R, G, B) color in the source GIF to replace with
            each presenter's tint color.
        tolerance: Per-channel tolerance for matching target_color.
        scale: Factor to scale frames by (1.0 = original size).

    Returns:
        Dict of {presenter_name: [pygame.Surface, ...]} with tinted frames,
        or empty dict if the GIF file is not found.
    """
    gif_path = Path(gif_path)
    if not gif_path.exists():
        print(f"  Speaker GIF not found: {gif_path}")
        return {}

    gif = Image.open(str(gif_path))
    raw_frames = []
    for i in range(gif.n_frames):
        gif.seek(i)
        frame = gif.convert("RGBA")
        raw_frames.append(frame)

    TARGET_R, TARGET_G, TARGET_B = target_color

    speaker_frames = {}
    for name, cfg in presenters.items():
        tint_r, tint_g, tint_b = cfg["color"]
        tinted = []
        for frame in raw_frames:
            pixels = frame.load()
            w, h = frame.size
            new_frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            new_pixels = new_frame.load()
            for y in range(h):
                for x in range(w):
                    r, g, b, a = pixels[x, y]
                    brightness = (r + g + b) / 3.0
                    if brightness < 30:
                        new_pixels[x, y] = (0, 0, 0, 0)
                    elif (
                        abs(r - TARGET_R) < tolerance
                        and abs(g - TARGET_G) < tolerance
                        and abs(b - TARGET_B) < tolerance
                    ):
                        factor = brightness / 255.0
                        nr = min(255, int(tint_r * factor))
                        ng = min(255, int(tint_g * factor))
                        nb = min(255, int(tint_b * factor))
                        new_pixels[x, y] = (nr, ng, nb, a)
                    else:
                        new_pixels[x, y] = (r, g, b, a)

            if scale != 1.0:
                new_w = int(w * scale)
                new_h = int(h * scale)
                new_frame = new_frame.resize((new_w, new_h), Image.NEAREST)

            data = new_frame.tobytes()
            surf = pygame.image.frombuffer(data, new_frame.size, "RGBA")
            tinted.append(surf)
        speaker_frames[name] = tinted
        print(f"  Speaker frames loaded: {name} ({len(tinted)} frames)")

    return speaker_frames
