from __future__ import annotations

from unittest.mock import MagicMock

from code_sensei.evaluation.retrieval_benchmark import (
    BenchmarkQuery,
    benchmark_queries_from_dicts,
    evaluate_queries,
)


def _make_hit(source_path: str, distance: float = 0.2) -> dict:
    return {
        "id": f"id-{source_path}",
        "document": "def fn(): pass",
        "metadata": {"source_path": source_path, "language": "python"},
        "distance": distance,
    }


def test_evaluate_queries_computes_recall_and_mrr():
    vector_store = MagicMock()
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1] * 4

    # First query: expected in rank 1, second query: expected in rank 2
    vector_store.query.side_effect = [
        [_make_hit("src/a.py", 0.1), _make_hit("src/b.py", 0.2)],
        [_make_hit("src/z.py", 0.1), _make_hit("src/target.py", 0.2)],
    ]

    from code_sensei.retrieval.retriever import Retriever

    retriever = Retriever(vector_store=vector_store, embedder=embedder, default_top_k=2)
    summary = evaluate_queries(
        retriever,
        [
            BenchmarkQuery(query="find a", expected_sources=["src/a.py"], top_k=2),
            BenchmarkQuery(query="find target", expected_sources=["src/target.py"], top_k=2),
        ],
    )

    assert summary.total_queries == 2
    assert summary.recall_at_k == 1.0
    assert summary.mean_reciprocal_rank == 0.75  # 1.0 and 0.5 average
    assert summary.pass_at_least_one_hit_rate == 1.0


def test_benchmark_queries_from_dicts_defaults_top_k():
    vector_store = MagicMock()
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1] * 4
    vector_store.query.return_value = [_make_hit("src/a.py", 0.1)]

    from code_sensei.retrieval.retriever import Retriever

    retriever = Retriever(vector_store=vector_store, embedder=embedder, default_top_k=3)
    summary = benchmark_queries_from_dicts(
        retriever,
        [{"query": "find a", "expected_sources": ["src/a.py"]}],
    )

    assert summary.total_queries == 1
    assert summary.recall_at_k == 1.0
    # Evaluator default top_k should be used when omitted in row.
    assert summary.cases[0].top_k == 8
