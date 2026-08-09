"""Answer generation grounded strictly in retrieved chunks.

OpenAI when configured; otherwise a deterministic composer that quotes the
retrieved passages with the same citation markers, so the whole chat flow —
streaming, citations, unanswered handling — runs offline and in tests.
"""

import logging
import re
from collections.abc import Iterator
from typing import Protocol

from app.core.config import get_settings
from app.rag.retrieval import RetrievedChunk

log = logging.getLogger(__name__)

HISTORY_EXCHANGES = 10  # context window per the scope appendix

SYSTEM_PROMPT = """You are the assistant of the Tomorrow Program platform.

Rules you must never break:
1. Answer ONLY from the numbered sources below. Never use outside knowledge.
2. If the sources do not cover the question, say so plainly and stop.
3. Cite every claim with its source marker, like [1] or [2].
4. Write your answer in the language of the QUESTION, never the language of the
   sources. An English question gets an English answer even when every source is
   in Hebrew, and a Hebrew question gets a Hebrew answer even when the sources
   are in English. Translate what the sources say into the question's language.
5. Be concise and practical; these are municipal staff at work.
6. Write plain prose. Do not use markdown headings, bold, italics, tables or
   code fences — they are read as literal asterisks and hashes, not formatting.
   When a genuine list helps, start each line with "- " and nothing else.
7. Put each citation in its own marker: [1][2], never [1, 2].
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


class ApiGeneration:
    """Any OpenAI-compatible chat endpoint: OpenAI, OpenRouter, and friends.

    Walks `llm_model_chain` in order — free tiers get rate-limited, and falling
    back to the next model beats showing the user an error.
    """

    def stream(
        self, question: str, chunks: list[RetrievedChunk], history: list[tuple[str, str]]
    ) -> Iterator[str]:
        from openai import OpenAI
        from openai.types.chat import ChatCompletionMessageParam

        settings = get_settings()
        headers = {}
        if settings.resolved_llm_base_url and "openrouter" in settings.resolved_llm_base_url:
            headers = {
                "HTTP-Referer": settings.openrouter_site_url or settings.nextauth_url,
                "X-Title": settings.openrouter_app_name,
            }
        client = OpenAI(
            api_key=settings.resolved_llm_key,
            base_url=settings.resolved_llm_base_url,
            default_headers=headers or None,
        )

        sources = "\n\n".join(f"[{i + 1}] {c.content}" for i, c in enumerate(chunks))
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"SOURCES:\n{sources}"},
        ]
        for role, content in history[-HISTORY_EXCHANGES * 2 :]:
            if role == "assistant":
                messages.append({"role": "assistant", "content": content})
            else:
                messages.append({"role": "user", "content": content})
        messages.append({"role": "user", "content": question})

        models = settings.llm_model_chain
        last_error: Exception | None = None
        for model in models:
            produced = False
            try:
                stream = client.chat.completions.create(
                    model=model, messages=messages, stream=True, temperature=0.2
                )
                for event in stream:
                    delta = event.choices[0].delta.content if event.choices else None
                    if delta:
                        produced = True
                        yield delta
                if produced:
                    return
                log.warning("model %s returned no content; trying next", model)
            except Exception as e:  # noqa: BLE001 — any provider error tries the next model
                if produced:
                    # tokens already reached the user; restarting would duplicate them
                    raise
                last_error = e
                log.warning("model %s failed (%s); trying next", model, e)
        raise RuntimeError(
            f"all configured models failed ({', '.join(models)})"
        ) from last_error


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
    if get_settings().resolved_llm_key:
        return ApiGeneration()
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
