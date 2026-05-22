"""Retrieval evaluation helpers for benchmark datasets."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from code_sensei.retrieval.retriever import RetrievalResult, Retriever


@dataclass
class BenchmarkQuery:
    """One benchmark query with expected source files."""

    query: str
    expected_sources: list[str]
    top_k: int = 8


@dataclass
class BenchmarkCaseResult:
    """Evaluation result for one benchmark query."""

    query: str
    top_k: int
    expected_sources: list[str]
    returned_sources: list[str]
    latency_ms: float
    hits_at_k: int
    recall_at_k: float
    reciprocal_rank: float


@dataclass
class BenchmarkSummary:
    """Aggregate metrics for a benchmark run."""

    total_queries: int
    avg_latency_ms: float
    recall_at_k: float
    mean_reciprocal_rank: float
    pass_at_least_one_hit_rate: float
    cases: list[BenchmarkCaseResult]


def evaluate_queries(
    retriever: Retriever,
    queries: list[BenchmarkQuery],
) -> BenchmarkSummary:
    """Evaluate retrieval quality/latency across benchmark queries."""
    cases: list[BenchmarkCaseResult] = []

    for item in queries:
        started = perf_counter()
        results = retriever.search(item.query, top_k=item.top_k)
        latency_ms = (perf_counter() - started) * 1000.0

        returned_sources = [r.source_path for r in results]
        expected = set(item.expected_sources)

        hits_at_k = sum(1 for src in returned_sources if src in expected)
        recall_at_k = (hits_at_k / len(expected)) if expected else 1.0

        reciprocal_rank = 0.0
        for idx, src in enumerate(returned_sources, start=1):
            if src in expected:
                reciprocal_rank = 1.0 / idx
                break

        cases.append(
            BenchmarkCaseResult(
                query=item.query,
                top_k=item.top_k,
                expected_sources=item.expected_sources,
                returned_sources=returned_sources,
                latency_ms=latency_ms,
                hits_at_k=hits_at_k,
                recall_at_k=recall_at_k,
                reciprocal_rank=reciprocal_rank,
            )
        )

    total = len(cases)
    if total == 0:
        return BenchmarkSummary(
            total_queries=0,
            avg_latency_ms=0.0,
            recall_at_k=0.0,
            mean_reciprocal_rank=0.0,
            pass_at_least_one_hit_rate=0.0,
            cases=[],
        )

    avg_latency = sum(c.latency_ms for c in cases) / total
    recall = sum(c.recall_at_k for c in cases) / total
    mrr = sum(c.reciprocal_rank for c in cases) / total
    hit_rate = sum(1 for c in cases if c.hits_at_k > 0) / total

    return BenchmarkSummary(
        total_queries=total,
        avg_latency_ms=avg_latency,
        recall_at_k=recall,
        mean_reciprocal_rank=mrr,
        pass_at_least_one_hit_rate=hit_rate,
        cases=cases,
    )


def benchmark_queries_from_dicts(
    retriever: Retriever,
    rows: list[dict],
) -> BenchmarkSummary:
    """Build benchmark queries from plain dict rows and evaluate them."""
    parsed = [
        BenchmarkQuery(
            query=str(r["query"]),
            expected_sources=list(r.get("expected_sources", [])),
            top_k=int(r.get("top_k", 8)),
        )
        for r in rows
    ]
    return evaluate_queries(retriever, parsed)
