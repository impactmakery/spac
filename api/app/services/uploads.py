"""Server-side upload validation: size cap, type detection, safe-preview classing.

Any file type may be uploaded — that is a deliberate product decision, so the
board can carry whatever a municipality needs to share. Two things still hold,
and neither restricts what you may upload:

1. The 25 MB cap.
2. Only a small set of types is ever rendered *inline* in the browser. Serving
   arbitrary HTML or SVG inline from the application's own domain would let one
   user's upload run script against another user's session — the platform
   attacking its own users. Everything outside that set downloads instead.
"""

import mimetypes

from fastapi import HTTPException

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB per PRD

# Extensions whose content type we pin rather than trust the browser for.
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "txt": "text/plain",
    "csv": "text/csv",
    "md": "text/markdown",
}

# Rendered in the browser. Deliberately excludes SVG and anything HTML-ish:
# both can carry script, and same-origin script is a session-stealing bug, not
# a file-type preference.
INLINE_SAFE = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}

# Text can be read for search; these are the ones the extractor understands.
EXTRACTABLE = {"pdf", "docx", "pptx", "xlsx", "png", "jpg", "jpeg", "webp", "gif",
               "txt", "csv", "md"}

FALLBACK_CONTENT_TYPE = "application/octet-stream"


def validate_upload(
    filename: str, content: bytes, declared_type: str, *, allow_any: bool = False
) -> tuple[str, str]:
    """Returns (extension, content type).

    `allow_any` is the board: people share whatever a colleague needs, so no type
    is refused there. Everywhere else keeps the known-type list, because the
    knowledge base and department areas exist to hold material the assistant
    reads — a binary in them is dead weight the assistant cannot use.

    The declared type from the browser is never trusted anywhere: it is
    attacker-supplied and decides how the file is later served.
    """
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in CONTENT_TYPES:
        if not allow_any:
            _check_magic(ext, content)
        return ext, CONTENT_TYPES[ext]

    if not allow_any:
        raise HTTPException(status_code=415, detail="unsupported_type")

    guessed, _ = mimetypes.guess_type(filename)
    # Anything we cannot pin is served as an opaque download, never rendered.
    return ext, guessed if guessed in INLINE_SAFE else FALLBACK_CONTENT_TYPE


# Signatures for the formats the curated surfaces accept, so a renamed file is
# caught rather than trusted on its extension.
_MAGIC = {
    "pdf": (b"%PDF",),
    "docx": (b"PK",),
    "pptx": (b"PK",),
    "xlsx": (b"PK",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "gif": (b"GIF87a", b"GIF89a"),
    "webp": (b"RIFF",),
}


def _check_magic(ext: str, content: bytes) -> None:
    prefixes = _MAGIC.get(ext)
    if prefixes and not any(content.startswith(p) for p in prefixes):
        raise HTTPException(status_code=415, detail="unsupported_type")


def is_inline_safe(content_type: str | None) -> bool:
    return content_type in INLINE_SAFE


def is_extractable(ext: str | None) -> bool:
    return (ext or "").lower() in EXTRACTABLE
