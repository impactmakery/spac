"""Turn a follow-up into a question that can stand on its own.

Generation sees the conversation, so an answer reads as if the assistant is
following along. Retrieval does not: it searches with the words of the current
question alone. So "and what about the size limit?" searches for those words,
matches almost nothing, and the assistant says the material does not cover it —
while appearing, in every other respect, to have been following the thread.

Rewriting closes that gap: the question becomes "what is the file upload size
limit?" before the search runs. The rewritten text is used *only* for
retrieval. Generation still receives the person's own words, so the answer
addresses what they actually asked.

This reads only the asker's own conversation, which they have already seen, so
it cannot widen what they can retrieve.
"""

import logging

log = logging.getLogger(__name__)

# Enough to resolve a reference, few enough to keep the prompt small. A
# pronoun almost always points at the last turn or two.
HISTORY_TURNS = 6
MAX_QUESTION_CHARS = 500

PROMPT = """Rewrite the user's latest question so it can be understood alone,
without the conversation.

Rules:
- Resolve pronouns and references ("that", "it", "there", "the same") into the
  thing they refer to, taken from the conversation.
- Keep the original language. A Hebrew question stays Hebrew.
- Change nothing else. Do not answer, explain, expand or add detail.
- If the question already stands on its own, return it unchanged.

Return only the rewritten question, with no preamble or quotation marks."""


def needs_rewriting(question: str, history: list[tuple[str, str]]) -> bool:
    """Whether it is worth spending a model call.

    A first question has nothing to resolve against, and an over-long one is
    usually already specific. Everything else is cheaper to rewrite than to
    answer badly.
    """
    if not history:
        return False
    return 0 < len(question.strip()) <= MAX_QUESTION_CHARS


def standalone_question(question: str, history: list[tuple[str, str]]) -> str:
    """The question as it should be searched for. Never raises.

    A failure here must not cost the person an answer, so anything unexpected
    falls back to their original wording — which is exactly the behaviour that
    existed before this function did.
    """
    if not needs_rewriting(question, history):
        return question

    try:
        from openai import OpenAI

        from app.core.config import get_settings

        settings = get_settings()
        if not settings.resolved_llm_key:
            return question

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

        conversation = "\n".join(
            f"{'User' if role == 'user' else 'Assistant'}: {content}"
            for role, content in history[-HISTORY_TURNS:]
        )
        for model in settings.llm_model_chain:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"Conversation so far:\n{conversation}\n\n"
                                f"Latest question: {question}"
                            ),
                        },
                    ],
                    temperature=0,
                    max_tokens=120,
                )
                rewritten = (response.choices[0].message.content or "").strip()
                rewritten = rewritten.strip("\"'").strip()
                # A model that returns nothing, an essay, or a refusal has not
                # given us a question — the original is better than a guess.
                if rewritten and len(rewritten) <= MAX_QUESTION_CHARS * 2:
                    return rewritten
            except Exception:  # noqa: BLE001 — try the next model in the chain
                continue
    except Exception as e:  # noqa: BLE001
        log.warning("query rewriting failed, searching the original: %s", e)

    return question
