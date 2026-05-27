"""
retrieval/retriever.py
----------------------
Semantic search over the indexed codebase.

Design notes
~~~~~~~~~~~~
* The ``Retriever`` composes the ``Embedder`` (for query embedding) and
  ``VectorStore`` (for similarity search).
* Results are ranked by cosine distance and optionally filtered by
  language or file-path prefix.
* ``RetrievalResult`` provides a clean interface for downstream modules
  (the assistant features) without leaking vector-store internals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from time import perf_counter

from ..indexer.embedder import Embedder
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class RetrievalMetrics:
    """Lightweight timings and outcome stats for a retrieval query."""

    query: str
    top_k: int
    language_filter: str | None
    path_prefix: str | None
    embed_ms: float
    vector_query_ms: float
    total_ms: float
    results_count: int
    avg_score: float


@dataclass
class RetrievalResult:
    """A single search result returned by the ``Retriever``."""

    chunk_id: str
    content: str
    source_path: str
    language: str
    score: float  # similarity score (1 - cosine distance); higher is better
    metadata: dict = field(default_factory=dict)

    @property
    def relevance_label(self) -> str:
        if self.score >= 0.90:
            return "very high"
        if self.score >= 0.75:
            return "high"
        if self.score >= 0.60:
            return "medium"
        return "low"


class Retriever:
    """
    Embeds a query and retrieves the most relevant code chunks.

    Parameters
    ----------
    vector_store:
        A connected ``VectorStore`` instance.
    embedder:
        An ``Embedder`` instance used to encode query strings.
    default_top_k:
        Default number of results to return.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: Embedder,
        default_top_k: int = 10,
    ) -> None:
        self.vector_store = vector_store
        self.embedder = embedder
        self.default_top_k = default_top_k
        self.last_metrics: RetrievalMetrics | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int | None = None,
        language_filter: str | None = None,
        path_prefix: str | None = None,
    ) -> list[RetrievalResult]:
        """
        Perform semantic search over the indexed codebase.

        Parameters
        ----------
        query:
            Natural-language or code query string.
        top_k:
            Maximum number of results to return (defaults to ``default_top_k``).
        language_filter:
            If set, only return chunks in the given language (e.g. ``"python"``).
        path_prefix:
            If set, only return chunks whose source path starts with this prefix.

        Returns
        -------
        list[RetrievalResult]
            Results ordered by descending similarity score.
        """
        started = perf_counter()
        k = top_k if top_k is not None else self.default_top_k
        embed_started = perf_counter()
        query_embedding = self.embedder.embed_query(query)
        embed_ms = (perf_counter() - embed_started) * 1000.0

        # Build optional ChromaDB ``where`` filter.
        where: dict | None = None
        if language_filter:
            where = {"language": language_filter}

        vector_query_started = perf_counter()
        raw_hits = self.vector_store.query(
            query_embedding=query_embedding,
            n_results=k,
            where=where,
        )
        vector_query_ms = (perf_counter() - vector_query_started) * 1000.0

        results: list[RetrievalResult] = []
        for hit in raw_hits:
            metadata = hit.get("metadata", {})
            source_path = metadata.get("source_path", "")

            # Apply path-prefix filter in Python (ChromaDB does not support prefix queries).
            if path_prefix and not source_path.startswith(path_prefix):
                continue

            distance = hit.get("distance", 1.0)
            # ChromaDB cosine distance is in [0, 2]; convert to similarity in [0, 1].
            score = max(0.0, min(1.0, 1.0 - distance / 2.0))

            results.append(
                RetrievalResult(
                    chunk_id=hit["id"],
                    content=hit["document"],
                    source_path=source_path,
                    language=metadata.get("language", ""),
                    score=score,
                    metadata=metadata,
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        avg_score = (sum(r.score for r in results) / len(results)) if results else 0.0
        total_ms = (perf_counter() - started) * 1000.0
        self.last_metrics = RetrievalMetrics(
            query=query,
            top_k=k,
            language_filter=language_filter,
            path_prefix=path_prefix,
            embed_ms=embed_ms,
            vector_query_ms=vector_query_ms,
            total_ms=total_ms,
            results_count=len(results),
            avg_score=avg_score,
        )
        logger.debug("Query '%s' returned %d results.", query[:60], len(results))
        return results
