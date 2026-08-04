"""Localized transactional emails (invite, password reset).

API-side email copy lives here in both languages; web UI strings live in
web/messages/*.json per project convention.
"""

from app.core.config import get_settings
from app.services.email import send_email

_RESET = {
    "he": {
        "subject": "איפוס סיסמה — סוכן מחר",
        "body": (
            '<div dir="rtl"><p>שלום {name},</p>'
            "<p>התקבלה בקשה לאיפוס הסיסמה שלך. הקישור תקף לשעה אחת:</p>"
            '<p><a href="{link}">לאיפוס הסיסמה</a></p>'
            "<p>אם לא ביקשת איפוס, אפשר להתעלם מהודעה זו.</p></div>"
        ),
    },
    "en": {
        "subject": "Password reset — Tomorrow Agent Hub",
        "body": (
            "<p>Hello {name},</p>"
            "<p>A password reset was requested for your account. The link is valid for one hour:</p>"
            '<p><a href="{link}">Reset your password</a></p>'
            "<p>If you did not request this, you can ignore this message.</p>"
        ),
    },
}

_INVITE = {
    "he": {
        "subject": "הוזמנת לסוכן מחר",
        "body": (
            '<div dir="rtl"><p>שלום,</p>'
            "<p>{inviter} הזמין/ה אותך להצטרף לפלטפורמת סוכן מחר{muni_part}.</p>"
            "<p>הקישור תקף לשבעה ימים:</p>"
            '<p><a href="{link}">להשלמת ההרשמה</a></p></div>'
        ),
        "muni_part": " עבור {muni}",
    },
    "en": {
        "subject": "You are invited to Tomorrow Agent Hub",
        "body": (
            "<p>Hello,</p>"
            "<p>{inviter} invited you to join the Tomorrow Agent Hub platform{muni_part}.</p>"
            "<p>The link is valid for seven days:</p>"
            '<p><a href="{link}">Complete your registration</a></p>'
        ),
        "muni_part": " for {muni}",
    },
}


def send_reset_email(*, to: str, name: str | None, language: str, raw_token: str) -> None:
    t = _RESET.get(language, _RESET["he"])
    link = f"{get_settings().nextauth_url}/{language}/reset-password?token={raw_token}"
    send_email(
        to=to, subject=t["subject"], html=t["body"].format(name=name or "", link=link)
    )


def send_invite_email(
    *,
    to: str,
    inviter_name: str | None,
    municipality_name: str | None,
    language: str,
    raw_token: str,
) -> None:
    t = _INVITE.get(language, _INVITE["he"])
    link = f"{get_settings().nextauth_url}/{language}/accept-invite?token={raw_token}"
    muni_part = t["muni_part"].format(muni=municipality_name) if municipality_name else ""
    send_email(
        to=to,
        subject=t["subject"],
        html=t["body"].format(inviter=inviter_name or "", muni_part=muni_part, link=link),
    )
