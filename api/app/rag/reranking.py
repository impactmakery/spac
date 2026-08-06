"""Re-ranking: reorder the fused candidates before they reach the prompt.

Retrieval optimises for *finding* passages; re-ranking optimises for *which
twelve* the model actually reads. Those are different jobs. Reciprocal Rank
Fusion knows only each arm's rank, so it happily returns six near-identical
chunks from one long document and drops the one paragraph from a second document
that would have completed the answer.

This stage runs entirely on rows the permission-filtered SQL already returned. It
can reorder and drop, never add — so it cannot widen what a user can see, and
that property is what makes it safe to iterate on.

The default reranker is deterministic and free: no model, no API call, no extra
latency. A cross-encoder would score better, but it means torch on an image that
was deliberately cut to 205 MB, so the interface is a protocol and the swap is a
config change rather than a rewrite.
"""

import math
import re
from typing import Protocol

# How much a candidate is penalised for repeating content already selected.
# 0 keeps pure relevance order; 1 maximises variety at the cost of relevance.
DIVERSITY = 0.35

# One document should not be able to fill the whole context window. A long report
# legitimately holds several relevant passages, but past six the marginal one is
# nearly always redundant with the first six — and redundant chunks are not free:
# they crowd out other sources and bias the model toward repeating one voice.
#
# The cap is strict. Returning eight varied passages beats twelve where four say
# the same thing, so when the cap binds the result is simply shorter.
MAX_PER_SOURCE = 6

_WORD = re.compile(r"\w+", re.UNICODE)


def _terms(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text) if len(w) > 2}


def _overlap(a: set[str], b: set[str]) -> float:
    """Jaccard overlap — 1.0 when two chunks say the same thing."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class Reranker(Protocol):
    def rerank(self, query: str, candidates: list, limit: int) -> list: ...


class HeuristicReranker:
    """Relevance, then variety, with a cap per source document.

    Relevance blends three signals that disagree usefully: the fused retrieval
    score (both arms' opinion), cosine similarity (meaning), and how much of the
    question's vocabulary the passage actually contains (literal coverage). A
    passage can win on any one of them, which is the point of having all three.
    """

    def rerank(self, query: str, candidates: list, limit: int) -> list:
        if len(candidates) <= 1:
            return candidates[:limit]

        query_terms = _terms(query)
        chunk_terms = [_terms(c.content) for c in candidates]

        # Fused scores are tiny (~1/60) and unbounded relative to each other;
        # normalise so the blend below is not dominated by whichever scale
        # happens to be larger.
        top_score = max((c.score for c in candidates), default=0.0) or 1.0

        base = []
        for candidate, terms in zip(candidates, chunk_terms, strict=True):
            coverage = len(query_terms & terms) / len(query_terms) if query_terms else 0.0
            base.append(
                0.5 * (candidate.score / top_score)
                + 0.3 * max(candidate.similarity, 0.0)
                + 0.2 * coverage
            )

        selected: list[int] = []
        selected_terms: list[set[str]] = []
        per_source: dict = {}
        remaining = set(range(len(candidates)))

        while remaining and len(selected) < limit:
            best_index, best_value = None, -math.inf
            for i in remaining:
                source = candidates[i].source_id
                if per_source.get(source, 0) >= MAX_PER_SOURCE:
                    continue
                redundancy = max(
                    (_overlap(chunk_terms[i], s) for s in selected_terms), default=0.0
                )
                value = base[i] - DIVERSITY * redundancy
                if value > best_value:
                    best_index, best_value = i, value

            if best_index is None:
                # Everything left is from a source already at its cap. Stop
                # rather than padding: filling the remaining slots with a
                # seventh passage from the same document is exactly the
                # crowding-out this stage exists to prevent.
                break

            selected.append(best_index)
            selected_terms.append(chunk_terms[best_index])
            source = candidates[best_index].source_id
            per_source[source] = per_source.get(source, 0) + 1
            remaining.discard(best_index)

        return [candidates[i] for i in selected[:limit]]


_reranker: Reranker = HeuristicReranker()


def get_reranker() -> Reranker:
    return _reranker


def rerank(query: str, candidates: list, limit: int) -> list:
    return get_reranker().rerank(query, candidates, limit)
