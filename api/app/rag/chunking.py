"""Token-based chunking: 800-token chunks with 150-token overlap (spec)."""

from functools import lru_cache

CHUNK_TOKENS = 800
CHUNK_OVERLAP = 150


@lru_cache
def _encoding():
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


def token_len(text: str) -> int:
    return len(_encoding().encode(text))


def chunk_text(
    text: str, max_tokens: int = CHUNK_TOKENS, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    text = text.strip()
    if not text:
        return []
    enc = _encoding()
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return [text]
    chunks = []
    step = max_tokens - overlap
    for start in range(0, len(tokens), step):
        window = tokens[start : start + max_tokens]
        chunks.append(enc.decode(window).strip())
        if start + max_tokens >= len(tokens):
            break
    return [c for c in chunks if c]
