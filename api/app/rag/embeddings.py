"""Embeddings: OpenAI (1536-dim truncated text-embedding-3-large) or a
deterministic fake when no API key is configured (dev + tests).

Model swap = env var change + re-embed job; no code change (spec).
"""

import hashlib
import math
import random
import re
from typing import Protocol

from app.core.config import get_settings
from app.models import EMBEDDING_DIM

BATCH_SIZE = 100  # chunks per embeddings call (spec)


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ApiEmbeddings:
    """Any OpenAI-compatible embeddings endpoint, batched per the spec.

    Always requests EMBEDDING_DIM dimensions so vectors match the `chunks`
    column; changing the model means re-embedding (scripts/reembed.py).
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI

        settings = get_settings()
        client = OpenAI(
            api_key=settings.resolved_embedding_key,
            base_url=settings.resolved_embedding_base_url,
        )
        out: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            res = client.embeddings.create(
                model=settings.embedding_model, input=batch, dimensions=EMBEDDING_DIM
            )
            out.extend(item.embedding for item in res.data)
        return out


class FakeEmbeddings:
    """Deterministic hashed bag-of-words vectors for offline dev and tests.

    Cosine similarity then tracks lexical overlap, so paraphrased questions
    retrieve their source passage and unrelated ones fall below the 0.35
    threshold — close enough in behaviour to exercise the whole RAG path
    without an API key. Real deployments use OpenAI embeddings.

    Two details keep it usable: only the most distinctive tokens are kept
    (longest first — short words carry little signal), and each kept token
    contributes equally. Without the cap, cosine would decay with passage
    length and long chunks would never clear the retrieval threshold, which
    is an artifact of bag-of-words, not of real embeddings.
    """

    MAX_FEATURES = 16

    STOPWORDS = frozenset(
        """a an and are as at be by for from how in is it of on or that the this to was what
        when where which who why with your you we our שלי שלך של הוא היא הם על עם את אל כי גם
        אבל או אם כל מה מי איך למה יש אין זה זו הזה הזו""".split()
    )

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    @classmethod
    def _tokens(cls, text: str) -> list[str]:
        raw = re.findall(r"[\w֐-׿]+", text.lower())
        kept = {
            t for t in raw if t not in cls.STOPWORDS and (len(t) >= 2 or t.isdigit())
        }
        # longest tokens first: a crude but stable stand-in for distinctiveness
        return sorted(kept, key=lambda t: (-len(t), t))[: cls.MAX_FEATURES]

    @classmethod
    def _one(cls, text: str) -> list[float]:
        vec = [0.0] * EMBEDDING_DIM
        tokens = cls._tokens(text)
        if not tokens:
            # keep unit norm so cosine stays defined for empty/stopword-only text
            seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
            rng = random.Random(seed)
            vec = [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]
        else:
            for token in tokens:
                idx = (
                    int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big")
                    % EMBEDDING_DIM
                )
                vec[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


def get_embedding_provider() -> EmbeddingProvider:
    if get_settings().resolved_embedding_key:
        return ApiEmbeddings()
    return FakeEmbeddings()
