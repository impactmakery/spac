"""Serves locally stored files via HMAC-signed expiring URLs (dev fallback for R2)."""

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response

from app.services.storage import LocalDiskProvider, verify_signed_path

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{key:path}")
def serve_file(key: str, exp: int, sig: str, name: str = "file") -> Response:
    if not verify_signed_path(key, exp, sig):
        raise HTTPException(status_code=404, detail="not_found")
    provider = LocalDiskProvider()
    try:
        data = provider.open(key)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="not_found") from None
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(name)}",
            "Cache-Control": "private, max-age=0",
        },
    )
