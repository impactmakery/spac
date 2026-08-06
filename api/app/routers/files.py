"""Serves locally stored files via HMAC-signed expiring URLs (dev fallback for R2)."""

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response

from app.services.storage import LocalDiskProvider, verify_signed_path
from app.services.uploads import is_inline_safe

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{key:path}")
def serve_file(
    key: str, exp: int, sig: str, name: str = "file", ct: str | None = None
) -> Response:
    if not verify_signed_path(key, exp, sig):
        raise HTTPException(status_code=404, detail="not_found")
    provider = LocalDiskProvider()
    try:
        data = provider.open(key)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="not_found") from None

    # This route serves from the application's own origin, so it is the one
    # place where rendering an uploaded file inline could run script against
    # another user's session. Any type may be uploaded; only a known-safe few
    # are rendered, and the rest download.
    inline = is_inline_safe(ct)
    return Response(
        content=data,
        media_type=ct if inline else "application/octet-stream",
        headers={
            "Content-Disposition": (
                f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(name)}"
            ),
            "Cache-Control": "private, max-age=0",
            # Belt and braces: stops a browser sniffing a download back into HTML.
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
