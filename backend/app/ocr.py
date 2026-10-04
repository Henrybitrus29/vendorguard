"""Text extraction with an OCR fallback.

Digital PDFs and text files are read directly. If a PDF yields almost no text (a scan), or the upload is an
image, the file is OCR'd with Tesseract. OCR output is UNTRUSTED like any other document text: faint or tiny
text in an image becomes machine-readable here, so it still goes through the injection scan downstream.
"""
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

MAX_CHARS = 200_000
MAX_PDF_PAGES = 100
MAX_IMAGE_PIXELS = 40_000_000  # refuse "decompression bomb" images
IMAGE_TYPES = {"image/png", "image/jpeg"}


@dataclass
class Extraction:
    text: str
    method: str  # digital | ocr | none
    ocr_pages: int = 0


def _digital_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        parts.append(page.extract_text() or "")
        if sum(len(p) for p in parts) > MAX_CHARS:
            break
    return "\n".join(parts)[:MAX_CHARS]


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def _ocr_image(img) -> str:
    import pytesseract

    return pytesseract.image_to_string(img, lang="eng", timeout=settings.ocr_page_timeout)


def _ocr_pdf(path: Path) -> tuple[str, int]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        parts: list[str] = []
        pages = 0
        for i in range(min(len(pdf), settings.ocr_max_pages)):
            page = pdf[i]
            width, height = page.get_size()
            scale = min(2.0, 2500 / max(width, height, 1))  # keep rendered pages a sane size
            image = page.render(scale=scale).to_pil().convert("L")
            parts.append(_ocr_image(image))
            pages += 1
            if sum(len(p) for p in parts) > MAX_CHARS:
                break
        return "\n".join(parts)[:MAX_CHARS], pages
    finally:
        pdf.close()


def _ocr_image_file(path: Path) -> tuple[str, int]:
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    with Image.open(path) as img:
        if img.width * img.height > MAX_IMAGE_PIXELS:
            raise ValueError("image is too large to process")
        return _ocr_image(img.convert("L"))[:MAX_CHARS], 1


def _try_ocr(fn: Callable[[], tuple[str, int]]) -> tuple[str, int]:
    """OCR must never crash the pipeline: any problem means 'no text', which the agent sends to a person."""
    if not settings.ocr_enabled:
        return "", 0
    if not ocr_available():
        log.warning("OCR is needed but the tesseract binary is not installed")
        return "", 0
    try:
        return fn()
    except Exception as exc:
        log.warning("OCR failed: %s", type(exc).__name__)
        return "", 0


def extract_document(path: Path, content_type: str) -> Extraction:
    if content_type == "application/pdf":
        try:
            text = _digital_pdf_text(path)
        except Exception as exc:
            log.warning("PDF text extraction failed: %s", type(exc).__name__)
            text = ""
        if len(text.strip()) >= settings.ocr_min_chars:
            return Extraction(text, "digital")
        ocr_text, pages = _try_ocr(lambda: _ocr_pdf(path))
        if ocr_text.strip():
            return Extraction(ocr_text, "ocr", pages)
        return Extraction(text, "digital" if text.strip() else "none")

    if content_type in IMAGE_TYPES:
        ocr_text, pages = _try_ocr(lambda: _ocr_image_file(path))
        return Extraction(ocr_text, "ocr" if ocr_text.strip() else "none", pages)

    return Extraction(path.read_text(encoding="utf-8", errors="replace")[:MAX_CHARS], "digital")
