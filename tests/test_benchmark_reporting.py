from __future__ import annotations

import json
from pathlib import Path

from code_sensei.evaluation.retrieval_benchmark import BenchmarkCaseResult, BenchmarkSummary
from scripts.report_retrieval_benchmark_delta import (
    append_warnings,
    build_markdown,
    collect_soft_regressions,
    main,
)


def test_build_markdown_contains_deltas():
    current = BenchmarkSummary(
        total_queries=3,
        avg_latency_ms=1.2,
        recall_at_k=1.0,
        mean_reciprocal_rank=0.9,
        pass_at_least_one_hit_rate=1.0,
        cases=[
            BenchmarkCaseResult(
                query="q",
                top_k=3,
                expected_sources=["a.py"],
                returned_sources=["a.py"],
                latency_ms=1.2,
                hits_at_k=1,
                recall_at_k=1.0,
                reciprocal_rank=1.0,
            )
        ],
    ).to_dict()
    baseline = {
        "total_queries": 3,
        "avg_latency_ms": 1.0,
        "recall_at_k": 0.8,
        "mean_reciprocal_rank": 0.7,
        "pass_at_least_one_hit_rate": 0.9,
    }

    markdown = build_markdown(current, baseline)

    assert "Retrieval Benchmark Delta" in markdown
    assert "+0.200" in markdown
    assert "mean_reciprocal_rank" in markdown


def test_report_script_supports_current_summary(tmp_path: Path, monkeypatch):
    current_summary = tmp_path / "current.json"
    baseline_summary = tmp_path / "baseline.json"
    output_md = tmp_path / "report.md"

    current_summary.write_text(
        json.dumps(
            {
                "total_queries": 3,
                "avg_latency_ms": 1.5,
                "recall_at_k": 1.0,
                "mean_reciprocal_rank": 0.9,
                "pass_at_least_one_hit_rate": 1.0,
                "cases": [],
            }
        ),
        encoding="utf-8",
    )
    baseline_summary.write_text(
        json.dumps(
            {
                "total_queries": 3,
                "avg_latency_ms": 1.0,
                "recall_at_k": 0.8,
                "mean_reciprocal_rank": 0.7,
                "pass_at_least_one_hit_rate": 0.9,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "report_retrieval_benchmark_delta.py",
            "--current-summary",
            str(current_summary),
            "--baseline",
            str(baseline_summary),
            "--output-md",
            str(output_md),
        ],
    )

    assert main() == 0
    report = output_md.read_text(encoding="utf-8")
    assert "Retrieval Benchmark Delta" in report
    assert "+0.500" in report


def test_collect_soft_regressions_and_append_warnings():
    current = {
        "total_queries": 3,
        "avg_latency_ms": 900.0,
        "recall_at_k": 0.5,
        "mean_reciprocal_rank": 0.4,
        "pass_at_least_one_hit_rate": 0.5,
    }
    baseline = {
        "total_queries": 3,
        "avg_latency_ms": 500.0,
        "recall_at_k": 0.8,
        "mean_reciprocal_rank": 0.7,
        "pass_at_least_one_hit_rate": 0.8,
    }

    warnings = collect_soft_regressions(current, baseline, 250.0, 0.10)
    markdown = append_warnings("report", warnings)

    assert warnings
    assert "avg_latency_ms regression exceeded threshold" in warnings[0]
    assert "Soft Regression Warnings" in markdown
