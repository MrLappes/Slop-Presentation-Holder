"""PDF slide rendering and text extraction using PyMuPDF (fitz)."""

from pathlib import Path

import fitz
import pygame


def load_slides_as_surfaces(pdf_path: Path, screen_w: int, screen_h: int) -> list:
    """Load all pages from a PDF as pygame surfaces scaled to fit the screen."""
    doc = fitz.open(str(pdf_path))
    surfaces = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        # calculate zoom to fit screen while maintaining aspect ratio
        page_rect = page.rect
        scale_x = screen_w / page_rect.width
        scale_y = screen_h / page_rect.height
        scale = min(scale_x, scale_y)
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat)
        mode = "RGBA" if pix.alpha else "RGB"
        img = pygame.image.frombuffer(pix.samples, (pix.width, pix.height), mode)
        surfaces.append(img)
    doc.close()
    return surfaces


def extract_slide_text(pdf_path: Path) -> list[str]:
    """Extract text content from each page of a PDF.

    Returns a list of strings, one per page.
    """
    doc = fitz.open(str(pdf_path))
    texts = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        texts.append(page.get_text())
    doc.close()
    return texts


def get_slide_count(pdf_path: Path) -> int:
    """Return the number of pages in a PDF."""
    doc = fitz.open(str(pdf_path))
    count = len(doc)
    doc.close()
    return count


def render_slide_thumbnail(pdf_path: Path, page: int, max_width: int = 200) -> bytes:
    """Render a single PDF page as a PNG thumbnail.

    Returns PNG bytes suitable for loading into a QPixmap.
    """
    doc = fitz.open(str(pdf_path))
    if page < 0 or page >= len(doc):
        doc.close()
        raise IndexError(f"Page {page} out of range (0-{len(doc) - 1})")

    pg = doc[page]
    page_rect = pg.rect
    scale = max_width / page_rect.width
    mat = fitz.Matrix(scale, scale)
    pix = pg.get_pixmap(matrix=mat)
    png_bytes = pix.tobytes("png")
    doc.close()
    return png_bytes
