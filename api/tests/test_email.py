import json


def test_outbox_provider_writes_json(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.services.email import send_email

    monkeypatch.setattr(get_settings(), "outbox_dir", str(tmp_path))
    send_email(to="x@example.org", subject="Hello", html="<b>Hi</b>")

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    body = json.loads(files[0].read_text(encoding="utf-8"))
    assert body == {"to": "x@example.org", "subject": "Hello", "html": "<b>Hi</b>"}


def test_outbox_used_when_no_resend_key():
    from app.core.config import get_settings
    from app.services.email import get_email_provider

    assert not get_settings().resend_api_key
    assert type(get_email_provider()).__name__ == "OutboxProvider"
