"""Conversational openers that are not questions about the material.

"Hi" is not an unanswered question: replying "the material does not cover this"
reads as broken, and logging it pollutes the unanswered-questions panel that
system administrators use to decide what to add to the knowledge base.

Matching is deliberately narrow — the whole message must be the pleasantry.
"Hi, when is waste collected?" is a real question and goes through retrieval.
"""

import re

MAX_SMALLTALK_CHARS = 60

GREETINGS = {
    "hi", "hello", "hey", "yo", "good morning", "good afternoon", "good evening",
    "hi there", "hello there", "morning", "greetings", "sup", "howdy",
    "שלום", "היי", "הי", "אהלן", "בוקר טוב", "צהריים טובים", "ערב טוב",
    "מה נשמע", "מה קורה", "שלום לך",
}

THANKS = {
    "thanks", "thank you", "thanks a lot", "thank you very much", "ty", "cheers",
    "appreciated", "thanks!", "great", "perfect", "nice", "ok thanks",
    "תודה", "תודה רבה", "מעולה", "יופי", "אחלה", "סבבה", "תודה לך",
}

CAPABILITIES = {
    "what can you do", "who are you", "what are you", "help", "what is this",
    "how do you work", "what do you know",
    "מה אתה יכול לעשות", "מי אתה", "מה אתה", "עזרה", "מה זה",
    "איך אתה עובד", "מה אתה יודע",
}

REPLIES = {
    "greeting": {
        "en": (
            "Hello. I am the Tomorrow Agent. I answer from the documents on this "
            "platform that you have access to — the knowledge base, the boards, "
            "and your department's files — and I cite the source for every answer. "
            "What would you like to know?"
        ),
        "he": (
            "שלום. אני סוכן מחר. אני עונה על סמך המסמכים שבפלטפורמה שיש לך גישה "
            "אליהם — בסיס מחר, הלוחות והקבצים של המחלקה שלך — ומציין את המקור לכל "
            "תשובה. במה אוכל לעזור?"
        ),
    },
    "thanks": {
        "en": "Happy to help. Ask me anything else about the material here.",
        "he": "בשמחה. אפשר לשאול אותי כל שאלה נוספת על החומרים כאן.",
    },
    "capabilities": {
        "en": (
            "I answer questions from the documents on this platform that you are "
            "allowed to see: the shared knowledge base, the boards, and your "
            "department's files. Every answer cites the document it came from, and "
            "when the material does not cover something I say so rather than guess. "
            "Try asking about a procedure, a form, or a policy."
        ),
        "he": (
            "אני עונה על שאלות מתוך המסמכים שבפלטפורמה שמותר לך לראות: בסיס מחר, "
            "הלוחות והקבצים של המחלקה שלך. כל תשובה מציינת את המסמך שממנו היא "
            "נלקחה, וכשהחומר אינו מכסה נושא — אני אומר זאת במקום לנחש. אפשר לשאול "
            "אותי על נוהל, טופס או מדיניות."
        ),
    },
}


def _normalise(text: str) -> str:
    cleaned = re.sub(r"[!?.,;:\s]+", " ", text.strip().lower())
    return cleaned.strip()


def classify(text: str) -> str | None:
    """Return 'greeting' | 'thanks' | 'capabilities', or None for a real question."""
    if len(text) > MAX_SMALLTALK_CHARS:
        return None
    normalised = _normalise(text)
    if not normalised:
        return None
    for kind, phrases in (
        ("greeting", GREETINGS),
        ("thanks", THANKS),
        ("capabilities", CAPABILITIES),
    ):
        if normalised in phrases:
            return kind
    return None


def reply(kind: str, language: str) -> str:
    return REPLIES[kind].get(language, REPLIES[kind]["he"])
