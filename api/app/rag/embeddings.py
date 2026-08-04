"""Embeddings: OpenAI (1536-dim truncated text-embedding-3-large) or a
deterministic fake when no API key is configured (dev + tests).

Model swap = env var change + re-embed job; no code change (spec).
"""

import hashlib
import math
import random
from typing import Protocol

from app.core.config import get_settings
from app.models import EMBEDDING_DIM

BATCH_SIZE = 100  # chunks per embeddings call (spec)


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbeddings:
    def embed(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI

        settings = get_settings()
        client = OpenAI(api_key=settings.openai_api_key)
        out: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            res = client.embeddings.create(
                model=settings.embedding_model, input=batch, dimensions=EMBEDDING_DIM
            )
            out.extend(item.embedding for item in res.data)
        return out


class FakeEmbeddings:
    """Deterministic unit vectors seeded by content hash. Identical texts collide
    exactly, similar texts do not — sufficient for tests and offline dev."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    @staticmethod
    def _one(text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
        rng = random.Random(seed)
        vec = [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


def get_embedding_provider() -> EmbeddingProvider:
    if get_settings().openai_api_key:
        return OpenAIEmbeddings()
    return FakeEmbeddings()
