"""Text extraction per format. Raises ExtractionError on unreadable files."""

import io


class ExtractionError(Exception):
    pass


def extract_text(content: bytes, ext: str) -> str:
    try:
        if ext == "pdf":
            return _pdf(content)
        if ext == "docx":
            return _docx(content)
        if ext == "pptx":
            return _pptx(content)
        if ext == "xlsx":
            return _xlsx(content)
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(str(e)) from e
    raise ExtractionError(f"unsupported extension: {ext}")


def _pdf(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


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
