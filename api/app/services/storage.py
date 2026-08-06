"""File storage: Cloudflare R2 when configured, local disk otherwise (dev/tests).

Downloads are always via short-lived URLs generated after a permission check:
R2 presigned GETs, or HMAC-signed paths served by /api/files/{key} locally.
"""

import hashlib
import hmac
import time
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from app.core.config import get_settings

DEFAULT_EXPIRES = 900  # 15 minutes per scope appendix


class StorageProvider(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def open(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def download_url(
        self,
        key: str,
        filename: str,
        expires_seconds: int = DEFAULT_EXPIRES,
        content_type: str | None = None,
    ) -> str: ...


def _sign(key: str, exp: int) -> str:
    secret = get_settings().jwt_secret.encode()
    return hmac.new(secret, f"{key}:{exp}".encode(), hashlib.sha256).hexdigest()


def verify_signed_path(key: str, exp: int, sig: str) -> bool:
    if exp < time.time():
        return False
    return hmac.compare_digest(_sign(key, exp), sig)


class LocalDiskProvider:
    @property
    def _root(self) -> Path:
        return Path(get_settings().files_dir)

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root.resolve()):
            raise ValueError("invalid storage key")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def open(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def download_url(
        self,
        key: str,
        filename: str,
        expires_seconds: int = DEFAULT_EXPIRES,
        content_type: str | None = None,
    ) -> str:
        exp = int(time.time()) + expires_seconds
        sig = _sign(key, exp)
        url = f"/api/files/{key}?exp={exp}&sig={sig}&name={quote(filename)}"
        if content_type:
            url += f"&ct={quote(content_type)}"
        return url


class R2Provider:
    def _client(self):
        import boto3

        s = get_settings()
        return boto3.client(
            "s3",
            endpoint_url=s.r2_endpoint_url,
            aws_access_key_id=s.r2_access_key_id,
            aws_secret_access_key=s.r2_secret_access_key,
            region_name="auto",
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client().put_object(
            Bucket=get_settings().r2_bucket, Key=key, Body=data, ContentType=content_type
        )

    def open(self, key: str) -> bytes:
        obj = self._client().get_object(Bucket=get_settings().r2_bucket, Key=key)
        return obj["Body"].read()

    def delete(self, key: str) -> None:
        self._client().delete_object(Bucket=get_settings().r2_bucket, Key=key)

    def download_url(
        self,
        key: str,
        filename: str,
        expires_seconds: int = DEFAULT_EXPIRES,
        content_type: str | None = None,
    ) -> str:
        # `inline` only for types we are willing to render — the document page
        # previews PDFs and images in the browser. Everything else downloads:
        # any file type may be uploaded, but serving an arbitrary one inline
        # from this origin would let one upload run script against another
        # user's session.
        from app.services.uploads import is_inline_safe

        disposition = "inline" if is_inline_safe(content_type) else "attachment"
        return self._client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": get_settings().r2_bucket,
                "Key": key,
                "ResponseContentDisposition": (
                    f"{disposition}; filename*=UTF-8''{quote(filename)}"
                ),
                # Stops a browser sniffing an opaque download back into HTML.
                "ResponseContentType": content_type or "application/octet-stream",
            },
            ExpiresIn=expires_seconds,
        )


def get_storage() -> StorageProvider:
    s = get_settings()
    if s.r2_account_id and s.r2_access_key_id and s.r2_secret_access_key:
        return R2Provider()
    return LocalDiskProvider()
