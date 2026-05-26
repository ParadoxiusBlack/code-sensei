from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from code_sensei.evaluation.retrieval_benchmark import benchmark_queries_from_dicts
from code_sensei.retrieval.retriever import RetrievalResult


class FixtureRetriever:
    def __init__(self, fixtures: dict[str, list[str]]) -> None:
        self.fixtures = fixtures

    def search(self, query: str, top_k: int | None = None) -> list[RetrievalResult]:
        sources = self.fixtures.get(query, [])
        limit = top_k if top_k is not None else len(sources)
        results: list[RetrievalResult] = []
        for idx, source in enumerate(sources[:limit]):
            results.append(
                RetrievalResult(
                    chunk_id=f"fixture-{idx}",
                    content="fixture content",
                    source_path=source,
                    language="python",
                    score=max(0.0, 1.0 - (idx * 0.1)),
                    metadata={},
                )
            )
        return results


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _metric_delta(current: float, baseline: float) -> str:
    delta = current - baseline
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.3f}"


def build_markdown(current: dict, baseline: dict) -> str:
    lines = [
        "## Retrieval Benchmark Delta",
        "",
        "| Metric | Current | Baseline | Delta |",
        "|---|---:|---:|---:|",
    ]
    for key in [
        "total_queries",
        "avg_latency_ms",
        "recall_at_k",
        "mean_reciprocal_rank",
        "pass_at_least_one_hit_rate",
    ]:
        current_value = float(current[key]) if key != "total_queries" else int(current[key])
        baseline_value = float(baseline[key]) if key != "total_queries" else int(baseline[key])
        delta = current_value - baseline_value
        delta_text = f"{delta:+.3f}" if key != "total_queries" else f"{delta:+d}"
        lines.append(f"| {key} | {current_value} | {baseline_value} | {delta_text} |")
    return "\n".join(lines) + "\n"


def collect_soft_regressions(
    current: dict,
    baseline: dict,
    max_latency_regression_ms: float | None,
    max_quality_drop: float | None,
) -> list[str]:
    """Collect non-blocking regression warnings for CI summaries."""
    warnings: list[str] = []

    if max_latency_regression_ms is not None:
        latency_delta = float(current["avg_latency_ms"]) - float(baseline["avg_latency_ms"])
        if latency_delta > max_latency_regression_ms:
            warnings.append(
                "avg_latency_ms regression exceeded threshold: "
                f"{latency_delta:.3f} ms > {max_latency_regression_ms:.3f} ms"
            )

    if max_quality_drop is not None:
        for key in ["recall_at_k", "mean_reciprocal_rank", "pass_at_least_one_hit_rate"]:
            drop = float(baseline[key]) - float(current[key])
            if drop > max_quality_drop:
                warnings.append(
                    f"{key} regression exceeded threshold: {drop:.3f} > {max_quality_drop:.3f}"
                )

    return warnings


def append_warnings(markdown: str, warnings: list[str]) -> str:
    if not warnings:
        return markdown
    lines = [markdown.rstrip(), "", "### Soft Regression Warnings", ""]
    lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate retrieval benchmark delta report.")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--results", default=None)
    parser.add_argument("--current-summary", default=None)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-md", default=None)
    parser.add_argument("--max-latency-regression-ms", type=float, default=None)
    parser.add_argument("--max-quality-drop", type=float, default=None)
    args = parser.parse_args()

    baseline = _load_json(Path(args.baseline))

    if args.current_summary:
        summary = _load_json(Path(args.current_summary))
    else:
        if not args.dataset or not args.results:
            raise SystemExit("Either --current-summary or both --dataset and --results are required.")
        dataset = _load_json(Path(args.dataset))
        fixture_results = _load_json(Path(args.results))
        summary = benchmark_queries_from_dicts(FixtureRetriever(fixture_results), dataset).to_dict()

    markdown = build_markdown(summary, baseline)
    warnings = collect_soft_regressions(
        summary,
        baseline,
        args.max_latency_regression_ms,
        args.max_quality_drop,
    )
    markdown = append_warnings(markdown, warnings)

    if args.output_json:
        Path(args.output_json).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if args.output_md:
        Path(args.output_md).write_text(markdown, encoding="utf-8")

    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(markdown)

    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
