"""
In-memory vector index for semantic memory search.

Uses TF-IDF bag-of-words vectors with cosine similarity.
No external dependencies required.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _tfidf_vector(
    tokens: list[str],
    doc_freq: dict[str, int],
    num_docs: int,
) -> dict[str, float]:
    if not tokens:
        return {}

    term_freq: dict[str, int] = {}
    for token in tokens:
        term_freq[token] = term_freq.get(token, 0) + 1

    vec: dict[str, float] = {}
    for term, count in term_freq.items():
        tf = count / len(tokens)
        idf = math.log((num_docs + 1) / (doc_freq.get(term, 0) + 1)) + 1
        vec[term] = tf * idf

    return vec


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0

    dot = sum(a.get(k, 0) * b.get(k, 0) for k in set(a) | set(b))
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


@dataclass
class SearchResult:
    """A single memory search hit."""

    key: str
    text: str
    score: float
    metadata: dict = field(default_factory=dict)


@dataclass
class VectorIndex:
    """
    Simple in-memory vector index backed by TF-IDF vectors.
    """

    _documents: dict[str, str] = field(default_factory=dict)
    _metadata: dict[str, dict] = field(default_factory=dict)

    def add(
        self,
        key: str,
        text: str,
        *,
        metadata: dict | None = None,
    ) -> None:
        self._documents[key] = text
        self._metadata[key] = metadata or {}

    def remove(self, key: str) -> None:
        self._documents.pop(key, None)
        self._metadata.pop(key, None)

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        min_score: float = 0.01,
    ) -> list[SearchResult]:
        if not self._documents:
            return []

        query_tokens = _tokenize(query)
        doc_freq: dict[str, int] = {}
        doc_tokens: dict[str, list[str]] = {}

        for key, text in self._documents.items():
            tokens = _tokenize(text)
            doc_tokens[key] = tokens
            for token in set(tokens):
                doc_freq[token] = doc_freq.get(token, 0) + 1

        num_docs = len(self._documents)
        query_vec = _tfidf_vector(query_tokens, doc_freq, num_docs)

        scored: list[SearchResult] = []
        for key, tokens in doc_tokens.items():
            doc_vec = _tfidf_vector(tokens, doc_freq, num_docs)
            score = _cosine(query_vec, doc_vec)
            if score >= min_score:
                scored.append(
                    SearchResult(
                        key=key,
                        text=self._documents[key],
                        score=score,
                        metadata=self._metadata.get(key, {}),
                    )
                )

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        return len(self._documents)
