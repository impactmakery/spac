"""Email delivery: Resend when configured, local JSON outbox otherwise (dev/tests)."""

import json
import re
import time
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class EmailProvider(Protocol):
    def send(self, *, to: str, subject: str, html: str) -> None: ...


class ResendProvider:
    def send(self, *, to: str, subject: str, html: str) -> None:
        import resend

        settings = get_settings()
        resend.api_key = settings.resend_api_key
        resend.Emails.send(
            {"from": settings.email_from, "to": [to], "subject": subject, "html": html}
        )


class OutboxProvider:
    def send(self, *, to: str, subject: str, html: str) -> None:
        outbox = Path(get_settings().outbox_dir)
        outbox.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", subject.lower())[:40] or "mail"
        path = outbox / f"{time.time_ns()}-{slug}.json"
        path.write_text(
            json.dumps({"to": to, "subject": subject, "html": html}, ensure_ascii=False),
            encoding="utf-8",
        )


def get_email_provider() -> EmailProvider:
    if get_settings().resend_api_key:
        return ResendProvider()
    return OutboxProvider()


def send_email(*, to: str, subject: str, html: str) -> None:
    get_email_provider().send(to=to, subject=subject, html=html)
