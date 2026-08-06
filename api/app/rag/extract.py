"""Text extraction per format. Raises ExtractionError on unreadable files.

Municipal archives are full of scanned paper: a PDF whose pages are images with
no text layer. Those extract to nothing and were previously marked
'not indexable'. When a PDF yields too little text to be plausible, the pages are
rasterised and run through Tesseract in Hebrew and English.
"""

import io
import logging

log = logging.getLogger(__name__)

# A born-digital page carries far more than this; anything less means the text
# layer is missing or decorative, and the real content is in the pixels.
MIN_CHARS_PER_PAGE = 40
OCR_MAX_PAGES = 40  # a 300-page scan would hold the worker for many minutes
OCR_DPI = 200  # below ~150 Hebrew diacritics and small print start to fail
OCR_LANGUAGES = "heb+eng"


class ExtractionError(Exception):
    pass


IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff", "tif"}
TEXT_EXTENSIONS = {"txt", "csv", "md", "markdown", "json", "yaml", "yml"}


def extract_text(content: bytes, ext: str) -> str:
    ext = (ext or "").lower()
    try:
        if ext == "pdf":
            return _pdf(content)
        if ext == "docx":
            return _docx(content)
        if ext == "pptx":
            return _pptx(content)
        if ext == "xlsx":
            return _xlsx(content)
        if ext in IMAGE_EXTENSIONS:
            return _image(content)
        if ext in TEXT_EXTENSIONS:
            return _plain(content)
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(str(e)) from e
    raise ExtractionError(f"unsupported extension: {ext}")


def _pdf(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    pages = [(page.extract_text() or "") for page in reader.pages]
    text = "\n\n".join(pages)

    if pages and len(text.strip()) < MIN_CHARS_PER_PAGE * len(pages):
        scanned = _ocr_pdf(content)
        # Keep whichever is richer: a mixed document (a born-digital report with
        # scanned appendices) should not lose its real text layer to a failed
        # OCR pass, and a pure scan should not keep its empty one.
        if len(scanned.strip()) > len(text.strip()):
            return scanned
    return text


def _image(content: bytes) -> str:
    """Read the words in a picture.

    A screenshot of a circular or a photographed notice is a real way people
    share information, and without this the assistant sees only the filename.
    Returns empty rather than raising when OCR is unavailable — an unreadable
    image is still a valid attachment.
    """
    try:
        import io as _io

        import pytesseract
        from PIL import Image
    except ImportError:
        log.info("image OCR skipped: pytesseract/Pillow not installed")
        return ""
    try:
        with Image.open(_io.BytesIO(content)) as image:
            return pytesseract.image_to_string(image, lang=OCR_LANGUAGES)
    except Exception as e:  # noqa: BLE001
        log.warning("image OCR failed: %s", e)
        return ""


def _plain(content: bytes) -> str:
    """Plain text, CSV, Markdown. Tries UTF-8 first, then Hebrew's legacy encoding."""
    for encoding in ("utf-8-sig", "utf-8", "cp1255", "iso-8859-8"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def ocr_available() -> bool:
    """Whether both halves of the OCR path are installed: the Python bindings
    and the Tesseract binary itself."""
    try:
        import pypdfium2  # noqa: F401
        import pytesseract

        pytesseract.get_tesseract_version()
    except Exception:  # noqa: BLE001 — any failure means the path is unusable
        return False
    return True


def _ocr_pdf(content: bytes) -> str:
    """Rasterise each page and read it with Tesseract.

    Deliberately never raises: OCR is a best-effort improvement on a document
    that already extracted to nothing, so a missing binary or a corrupt page
    must not turn a merely-empty document into a failed ingestion job.
    """
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except ImportError:
        log.info("OCR skipped: pypdfium2/pytesseract not installed")
        return ""

    try:
        pdf = pdfium.PdfDocument(io.BytesIO(content))
    except Exception as e:  # noqa: BLE001
        log.warning("OCR skipped: could not open PDF for rasterising: %s", e)
        return ""

    out: list[str] = []
    try:
        count = min(len(pdf), OCR_MAX_PAGES)
        if len(pdf) > OCR_MAX_PAGES:
            log.warning(
                "OCR limited to the first %d of %d pages", OCR_MAX_PAGES, len(pdf)
            )
        for index in range(count):
            try:
                page = pdf[index]
                image = page.render(scale=OCR_DPI / 72).to_pil()
                out.append(pytesseract.image_to_string(image, lang=OCR_LANGUAGES))
            except Exception as e:  # noqa: BLE001 — one bad page is not a failure
                log.warning("OCR failed on page %d: %s", index + 1, e)
    finally:
        pdf.close()

    return "\n\n".join(part for part in out if part.strip())


def _docx(content: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(content))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(part for part in parts if part.strip())


def _pptx(content: bytes) -> str:
    import pptx

    prs = pptx.Presentation(io.BytesIO(content))
    parts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                parts.append(shape.text_frame.text)
    return "\n".join(part for part in parts if part.strip())


def _xlsx(content: bytes) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    parts = []
    for ws in wb.worksheets:
        parts.append(str(ws.title))
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)
