"""
tests/test_retriever.py
-----------------------
Unit tests for code_sensei.retrieval.retriever.

The vector store and embedder are mocked so no external services are needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from code_sensei.retrieval.retriever import RetrievalResult, Retriever


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_mock_hit(
    doc_id="abc123",
    document="def foo(): pass",
    source_path="/src/foo.py",
    language="python",
    distance=0.2,
) -> dict:
    return {
        "id": doc_id,
        "document": document,
        "metadata": {
            "source_path": source_path,
            "language": language,
        },
        "distance": distance,
    }


@pytest.fixture()
def mock_vector_store():
    vs = MagicMock()
    vs.query.return_value = [
        _make_mock_hit("id1", "def add(a, b): return a + b", "/src/math.py", "python", 0.1),
        _make_mock_hit("id2", "def multiply(a, b): return a * b", "/src/math.py", "python", 0.3),
        _make_mock_hit("id3", "const x = 1;", "/src/app.js", "javascript", 0.5),
    ]
    return vs


@pytest.fixture()
def mock_embedder():
    emb = MagicMock()
    emb.embed_query.return_value = [0.1] * 1536
    return emb


@pytest.fixture()
def retriever(mock_vector_store, mock_embedder):
    return Retriever(
        vector_store=mock_vector_store,
        embedder=mock_embedder,
        default_top_k=5,
    )


# ---------------------------------------------------------------------------
# RetrievalResult
# ---------------------------------------------------------------------------


class TestRetrievalResult:
    def test_relevance_label_very_high(self):
        r = RetrievalResult("id", "x", "/src/f.py", "python", score=0.95)
        assert r.relevance_label == "very high"

    def test_relevance_label_high(self):
        r = RetrievalResult("id", "x", "/src/f.py", "python", score=0.80)
        assert r.relevance_label == "high"

    def test_relevance_label_medium(self):
        r = RetrievalResult("id", "x", "/src/f.py", "python", score=0.65)
        assert r.relevance_label == "medium"

    def test_relevance_label_low(self):
        r = RetrievalResult("id", "x", "/src/f.py", "python", score=0.40)
        assert r.relevance_label == "low"


# ---------------------------------------------------------------------------
# Retriever.search
# ---------------------------------------------------------------------------


class TestRetriever:
    def test_returns_list_of_results(self, retriever):
        results = retriever.search("arithmetic functions")
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, RetrievalResult) for r in results)

    def test_calls_embed_query(self, retriever, mock_embedder):
        retriever.search("some query")
        mock_embedder.embed_query.assert_called_once_with("some query")

    def test_calls_vector_store_query(self, retriever, mock_vector_store):
        retriever.search("some query", top_k=3)
        mock_vector_store.query.assert_called_once()
        call_kwargs = mock_vector_store.query.call_args.kwargs
        assert call_kwargs["n_results"] == 3

    def test_results_sorted_by_score_descending(self, retriever):
        results = retriever.search("query")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_score_is_in_zero_to_one_range(self, retriever):
        results = retriever.search("query")
        for r in results:
            assert 0.0 <= r.score <= 1.0

    def test_path_prefix_filter(self, retriever):
        results = retriever.search("query", path_prefix="/src/math.py")
        for r in results:
            assert r.source_path.startswith("/src/math.py")

    def test_language_filter_passed_to_vector_store(self, retriever, mock_vector_store):
        retriever.search("query", language_filter="python")
        call_kwargs = mock_vector_store.query.call_args.kwargs
        assert call_kwargs.get("where") == {"language": "python"}

    def test_no_language_filter_passes_none(self, retriever, mock_vector_store):
        retriever.search("query")
        call_kwargs = mock_vector_store.query.call_args.kwargs
        assert call_kwargs.get("where") is None

    def test_source_path_populated(self, retriever):
        results = retriever.search("query")
        assert all(r.source_path for r in results)

    def test_default_top_k_used_when_none(self, retriever, mock_vector_store):
        retriever.search("query")
        call_kwargs = mock_vector_store.query.call_args.kwargs
        assert call_kwargs["n_results"] == retriever.default_top_k

    def test_empty_results_handled(self, mock_embedder, mock_vector_store):
        mock_vector_store.query.return_value = []
        r = Retriever(vector_store=mock_vector_store, embedder=mock_embedder)
        results = r.search("nothing")
        assert results == []

    def test_last_metrics_populated(self, retriever):
        retriever.search("metrics query", top_k=4)
        metrics = retriever.last_metrics
        assert metrics is not None
        assert metrics.query == "metrics query"
        assert metrics.top_k == 4
        assert metrics.results_count >= 0
        assert metrics.total_ms >= 0.0
        assert metrics.embed_ms >= 0.0
        assert metrics.vector_query_ms >= 0.0
