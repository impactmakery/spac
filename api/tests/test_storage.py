import pytest


@pytest.fixture()
def local_storage(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.services.storage import LocalDiskProvider

    monkeypatch.setattr(get_settings(), "files_dir", str(tmp_path))
    return LocalDiskProvider()


def test_put_open_delete_roundtrip(local_storage):
    local_storage.put("kb/abc/doc.pdf", b"%PDF-1.4 test", "application/pdf")
    assert local_storage.open("kb/abc/doc.pdf") == b"%PDF-1.4 test"
    local_storage.delete("kb/abc/doc.pdf")
    with pytest.raises(FileNotFoundError):
        local_storage.open("kb/abc/doc.pdf")


def test_signed_url_valid_and_tamper_proof(local_storage):
    from app.services.storage import verify_signed_path

    url = local_storage.download_url("kb/abc/doc.pdf", "doc.pdf", expires_seconds=900)
    assert url.startswith("/api/files/kb/abc/doc.pdf?")
    from urllib.parse import parse_qs, urlparse

    q = parse_qs(urlparse(url).query)
    exp, sig = int(q["exp"][0]), q["sig"][0]
    assert verify_signed_path("kb/abc/doc.pdf", exp, sig)
    assert not verify_signed_path("kb/abc/OTHER.pdf", exp, sig)
    assert not verify_signed_path("kb/abc/doc.pdf", exp + 1, sig)


def test_signed_url_expiry(local_storage, monkeypatch):
    import time as time_mod

    from app.services import storage as storage_mod
    from app.services.storage import verify_signed_path

    url = local_storage.download_url("k", "f.pdf", expires_seconds=10)
    from urllib.parse import parse_qs, urlparse

    q = parse_qs(urlparse(url).query)
    exp, sig = int(q["exp"][0]), q["sig"][0]
    future = time_mod.time() + 3600
    monkeypatch.setattr(storage_mod.time, "time", lambda: future)
    assert not verify_signed_path("k", exp, sig)


def test_provider_selection_local_when_no_r2():
    from app.services.storage import LocalDiskProvider, get_storage

    assert isinstance(get_storage(), LocalDiskProvider)
