"""OCR fallback. Logic tests use fakes; the 'real' tests run Tesseract and are skipped if it is not installed."""
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

from app import ocr

needs_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract is not installed")
LONG_TEXT = "Master Services Agreement. Tax ID: 12-3456789. The vendor shall indemnify the client. " * 2


def make_scan(path, lines=("MASTER SERVICES AGREEMENT", "Tax ID: 12-3456789", "Vendor shall indemnify the client")):
    img = Image.new("L", (1400, 500), 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=44)
    for i, line in enumerate(lines):
        draw.text((40, 40 + i * 90), line, fill=0, font=font)
    img.save(path)
    return img


def test_digital_pdf_does_not_trigger_ocr(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr, "_digital_pdf_text", lambda p: LONG_TEXT)
    monkeypatch.setattr(ocr, "_ocr_pdf", lambda p: pytest.fail("OCR must not run for digital PDFs"))
    result = ocr.extract_document(tmp_path / "x.pdf", "application/pdf")
    assert result.method == "digital" and result.text == LONG_TEXT


def test_short_text_triggers_ocr(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr, "_digital_pdf_text", lambda p: "ab")
    monkeypatch.setattr(ocr, "ocr_available", lambda: True)
    monkeypatch.setattr(ocr, "_ocr_pdf", lambda p: (LONG_TEXT, 2))
    result = ocr.extract_document(tmp_path / "x.pdf", "application/pdf")
    assert (result.method, result.ocr_pages) == ("ocr", 2)


def test_missing_tesseract_degrades_to_no_text(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr, "_digital_pdf_text", lambda p: "")
    monkeypatch.setattr(ocr, "ocr_available", lambda: False)
    result = ocr.extract_document(tmp_path / "x.pdf", "application/pdf")
    assert result.method == "none" and result.text == ""


def test_ocr_can_be_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr.settings, "ocr_enabled", False)
    monkeypatch.setattr(ocr, "_digital_pdf_text", lambda p: "")
    monkeypatch.setattr(ocr, "_ocr_pdf", lambda p: pytest.fail("OCR is disabled"))
    assert ocr.extract_document(tmp_path / "x.pdf", "application/pdf").method == "none"


def test_ocr_crash_never_propagates(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr, "_digital_pdf_text", lambda p: "")
    monkeypatch.setattr(ocr, "ocr_available", lambda: True)

    def boom(_):
        raise RuntimeError("tesseract exploded")

    monkeypatch.setattr(ocr, "_ocr_pdf", boom)
    assert ocr.extract_document(tmp_path / "x.pdf", "application/pdf").method == "none"


@needs_tesseract
def test_real_ocr_reads_a_png(tmp_path):
    path = tmp_path / "scan.png"
    make_scan(path)
    result = ocr.extract_document(path, "image/png")
    assert result.method == "ocr" and "12-3456789" in result.text.replace(" ", "")


@needs_tesseract
def test_real_ocr_reads_a_scanned_pdf(tmp_path):
    path = tmp_path / "scan.pdf"
    make_scan(tmp_path / "tmp.png").save(path, "PDF")  # an image-only PDF has no text layer
    result = ocr.extract_document(path, "application/pdf")
    assert result.method == "ocr" and result.ocr_pages == 1
    assert "12-3456789" in result.text.replace(" ", "")


@needs_tesseract
def test_blank_image_gives_no_text(tmp_path):
    path = tmp_path / "blank.png"
    Image.new("L", (300, 300), 255).save(path)
    assert ocr.extract_document(path, "image/png").method == "none"


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
def test_oversized_image_is_refused(tmp_path):
    path = tmp_path / "huge.png"
    Image.new("1", (7000, 7000), 1).save(path)  # 49 million pixels
    with pytest.raises(ValueError):
        ocr._ocr_image_file(path)
