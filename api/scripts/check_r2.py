"""Verify R2 credentials end to end before trusting them with real uploads.

Round-trips a small object: put -> open -> presigned GET over HTTPS -> delete.
Run after setting R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / R2_BUCKET.

Usage: python scripts/check_r2.py
"""

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.services.storage import LocalDiskProvider, get_storage  # noqa: E402

KEY = "healthcheck/r2-roundtrip.txt"
BODY = b"tomorrow-agent-hub r2 roundtrip"


def main() -> None:
    settings = get_settings()
    storage = get_storage()
    if isinstance(storage, LocalDiskProvider):
        sys.exit(
            "R2 is not configured — storage is falling back to local disk.\n"
            "Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET."
        )

    print(f"bucket   : {settings.r2_bucket}")
    print(f"endpoint : https://{settings.r2_account_id}.r2.cloudflarestorage.com")

    storage.put(KEY, BODY, "text/plain")
    print("put      : ok")

    got = storage.open(KEY)
    assert got == BODY, f"content mismatch: {got!r}"
    print("open     : ok")

    url = storage.download_url(KEY, "roundtrip.txt", expires_seconds=120)
    with urllib.request.urlopen(url, timeout=30) as res:
        fetched = res.read()
        disposition = res.headers.get("Content-Disposition", "")
    assert fetched == BODY, "presigned download returned different content"
    print(f"presigned: ok ({disposition or 'no disposition header'})")

    storage.delete(KEY)
    try:
        storage.open(KEY)
    except Exception:
        print("delete   : ok")
    else:
        sys.exit("delete failed — object still readable")

    print("\nR2 is working.")


if __name__ == "__main__":
    main()
