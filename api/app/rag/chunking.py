"""Structure-aware chunking: 800 tokens with 150 overlap (spec), but cut at
paragraph boundaries rather than blindly mid-sentence.

Extracted documents keep their paragraph structure, and a chunk that ends
half-way through a clause embeds poorly and reads badly when cited. So blocks
are packed up to the limit and only split when a single block is itself too
long. Passing the document title prepends it to every chunk, which both
sharpens the embedding and makes a quoted passage identifiable.
"""

from functools import lru_cache

CHUNK_TOKENS = 800
CHUNK_OVERLAP = 150


@lru_cache
def _encoding():
    import tiktoken

    return tiktoken.get_encoding("cl100k_base")


def token_len(text: str) -> int:
    return len(_encoding().encode(text))


def _split_long_block(block: str, max_tokens: int, overlap: int) -> list[str]:
    """Fall back to token windows for a single block that exceeds the limit —
    a long table or an unbroken wall of text."""
    enc = _encoding()
    tokens = enc.encode(block)
    if len(tokens) <= max_tokens:
        return [block]
    pieces = []
    step = max(1, max_tokens - overlap)
    for start in range(0, len(tokens), step):
        window = tokens[start : start + max_tokens]
        piece = enc.decode(window).strip()
        if piece:
            pieces.append(piece)
        if start + max_tokens >= len(tokens):
            break
    return pieces


def chunk_text(
    text: str,
    max_tokens: int = CHUNK_TOKENS,
    overlap: int = CHUNK_OVERLAP,
    *,
    title: str | None = None,
) -> list[str]:
    text = text.strip()
    heading = title.strip() if title else ""
    prefix = f"{heading}\n\n" if heading else ""
    if not text:
        # a titled source with no extractable body (a link item, an image-only
        # PDF) is still worth one chunk — otherwise it is unsearchable
        return [heading] if heading else []

    budget = max_tokens - token_len(prefix) if prefix else max_tokens
    budget = max(budget, max_tokens // 2)  # a pathological title cannot starve content

    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if not blocks:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for block in blocks:
        block_tokens = token_len(block)

        if block_tokens > budget:
            if current:
                chunks.append("\n\n".join(current))
                current, current_tokens = [], 0
            chunks.extend(_split_long_block(block, budget, overlap))
            continue

        if current and current_tokens + block_tokens > budget:
            chunks.append("\n\n".join(current))
            # carry the tail of the previous chunk so context spans the seam
            carry: list[str] = []
            carried = 0
            for previous in reversed(current):
                previous_tokens = token_len(previous)
                if carried + previous_tokens > overlap:
                    break
                carry.insert(0, previous)
                carried += previous_tokens
            current, current_tokens = carry, carried

        current.append(block)
        current_tokens += block_tokens

    if current:
        chunks.append("\n\n".join(current))

    return [prefix + c for c in chunks if c.strip()]
