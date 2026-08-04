"""Server-side upload validation: extension whitelist, magic-byte sniff, size cap."""

from fastapi import HTTPException

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB per PRD

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def validate_upload(filename: str, content: bytes, declared_type: str) -> tuple[str, str]:
    """Returns (extension, canonical content type) or raises 413/415."""
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="unsupported_type")
    if ext == "pdf":
        if not content.startswith(b"%PDF"):
            raise HTTPException(status_code=415, detail="unsupported_type")
    elif not content.startswith(b"PK"):  # ooxml formats are zip containers
        raise HTTPException(status_code=415, detail="unsupported_type")
    return ext, CONTENT_TYPES[ext]
