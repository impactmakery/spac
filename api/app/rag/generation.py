"""Answer generation grounded strictly in retrieved chunks.

OpenAI when configured; otherwise a deterministic composer that quotes the
retrieved passages with the same citation markers, so the whole chat flow —
streaming, citations, unanswered handling — runs offline and in tests.
"""

import re
from collections.abc import Iterator
from typing import Protocol

from app.core.config import get_settings
from app.rag.retrieval import RetrievedChunk

HISTORY_EXCHANGES = 10  # context window per the scope appendix

SYSTEM_PROMPT = """You are the assistant of the Tomorrow Program platform.

Rules you must never break:
1. Answer ONLY from the numbered sources below. Never use outside knowledge.
2. If the sources do not cover the question, say so plainly and stop.
3. Cite every claim with its source marker, like [1] or [2].
4. Answer in the same language as the question (Hebrew question -> Hebrew answer).
5. Be concise and practical; these are municipal staff at work.
"""

NOT_COVERED = {
    "he": "החומר הזמין לך אינו מכסה את השאלה הזו. אפשר לבדוק בבסיס מחר או לפנות למנהל/ת שלך.",
    "en": (
        "The material available to you does not cover this question. "
        "You can check the Knowledge Base or ask your administrator."
    ),
}


def detect_language(question: str) -> str:
    return "he" if re.search(r"[֐-׿]", question) else "en"


def not_covered_reply(question: str) -> str:
    return NOT_COVERED[detect_language(question)]


def build_prompt(
    question: str, chunks: list[RetrievedChunk], history: list[tuple[str, str]]
) -> str:
    sources = "\n\n".join(
        f"[{i + 1}] {c.content}" for i, c in enumerate(chunks)
    )
    convo = "\n".join(f"{role}: {content}" for role, content in history)
    return (
        f"{SYSTEM_PROMPT}\n\nSOURCES:\n{sources}\n\n"
        f"{('CONVERSATION SO FAR:' + chr(10) + convo + chr(10) + chr(10)) if convo else ''}"
        f"QUESTION: {question}"
    )


class GenerationProvider(Protocol):
    def stream(
        self, question: str, chunks: list[RetrievedChunk], history: list[tuple[str, str]]
    ) -> Iterator[str]: ...


class OpenAIGeneration:
    def stream(
        self, question: str, chunks: list[RetrievedChunk], history: list[tuple[str, str]]
    ) -> Iterator[str]:
        from openai import OpenAI

        settings = get_settings()
        client = OpenAI(api_key=settings.openai_api_key)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        sources = "\n\n".join(f"[{i + 1}] {c.content}" for i, c in enumerate(chunks))
        messages.append({"role": "system", "content": f"SOURCES:\n{sources}"})
        for role, content in history[-HISTORY_EXCHANGES * 2 :]:
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": question})

        stream = client.chat.completions.create(
            model=settings.llm_model, messages=messages, stream=True, temperature=0.2
        )
        for event in stream:
            delta = event.choices[0].delta.content if event.choices else None
            if delta:
                yield delta


class FakeGeneration:
    """Deterministic, grounded, citation-bearing answers for offline dev and tests."""

    LEAD = {
        "he": "על סמך החומר הזמין לך:",
        "en": "Based on the material available to you:",
    }

    def stream(
        self, question: str, chunks: list[RetrievedChunk], history: list[tuple[str, str]]
    ) -> Iterator[str]:
        lang = detect_language(question)
        yield self.LEAD[lang]
        for i, chunk in enumerate(chunks[:3]):
            excerpt = " ".join(chunk.content.split())[:280]
            yield f"\n\n{excerpt} [{i + 1}]"


def get_generation_provider() -> GenerationProvider:
    if get_settings().openai_api_key:
        return OpenAIGeneration()
    return FakeGeneration()


def stream_answer(
    question: str,
    chunks: list[RetrievedChunk],
    history: list[tuple[str, str]] | None = None,
) -> Iterator[str]:
    """Stream an answer. Callers must never invoke this with an empty chunk list:
    empty retrieval returns the standard not-covered reply instead."""
    if not chunks:
        raise ValueError("stream_answer requires at least one retrieved chunk")
    return get_generation_provider().stream(question, chunks, history or [])
