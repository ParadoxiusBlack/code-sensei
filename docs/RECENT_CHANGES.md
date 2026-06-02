# Recent Changes and Why They Were Made

This document explains the most recent project updates in practical terms so contributors can quickly understand what changed, what problem each change solves, and how the pieces fit together.

## Current Focus

Recent work concentrated on making CodeSensei easier to trust during day-to-day development:

- retrieval quality is now measurable
- runtime behavior is easier to observe
- CI can catch regressions earlier
- generated benchmark artifacts no longer pollute retrieval results
- GUI behavior has stronger regression coverage

## 1. Retrieval Benchmarking

### What changed

- Added `src/code_sensei/evaluation/retrieval_benchmark.py`
- Added the `code-sensei benchmark-retrieval` CLI command
- Added benchmark datasets and a maintained CI baseline under `benchmarks/retrieval/`

### Why it was made

Before this work, retrieval quality could improve or regress without a reliable way to prove it. The new benchmark flow gives the project a repeatable way to measure Recall@k, MRR, hit rate, and latency against known queries so retrieval changes can be evaluated with evidence instead of guesswork.

## 2. Runtime Metrics for `ask` and `index`

### What changed

- `ask` now reports timing and retrieval quality context
- `index` now reports throughput and chunking metrics

### Why it was made

The CLI previously told users the command succeeded, but not where time was being spent. The added metrics make performance tuning easier, help explain slow runs, and provide quick feedback when retrieval breadth or indexing behavior changes.

## 3. CI Retrieval Delta Reporting

### What changed

- `.github/workflows/ci.yml` now runs linting, formatting, type checks, tests, and a real retrieval benchmark job
- CI provisions Ollama, indexes the repository, runs the smoke benchmark, and produces a delta report
- `scripts/report_retrieval_benchmark_delta.py` compares current results to the maintained baseline
- soft warning thresholds were added for latency and retrieval quality regressions

### Why it was made

Normal unit tests validate behavior, but they do not show whether retrieval quality drifts over time. The benchmark delta job closes that gap by turning retrieval regressions into visible CI feedback while keeping small fluctuations non-blocking.

## 4. Benchmark Artifact Exclusions During Indexing

### What changed

The default indexing flow now ignores:

- `benchmarks/`
- `retrieval-benchmark-summary.json`
- `retrieval-benchmark-summary.md`

### Why it was made

Benchmark inputs and generated reports contain vocabulary that can dominate retrieval results for benchmark-themed queries. Excluding them keeps the index focused on implementation files and reduces false relevance caused by test or report artifacts.

## 5. GUI Regression Coverage

### What changed

- Added end-to-end GUI workflow coverage in `tests/test_gui_e2e.py`

### Why it was made

The GUI now covers enough user behavior that component-level tests alone are not sufficient. End-to-end coverage helps catch regressions in startup, ask flow, source selection, chunk comparison, and export behavior before they ship.

## 6. What These Changes Mean for Contributors

If you change retrieval, indexing, or benchmark logic, you should expect to:

1. run the normal quality checks
2. consider benchmark impact, not just correctness
3. avoid indexing generated benchmark artifacts
4. update benchmark datasets or baselines only when the retrieval behavior change is intentional

## 7. Current Verified Baseline

The repository was revalidated while preparing this documentation with the same commands used in CI:

- `ruff check src tests`
- `black --check src tests`
- `mypy src`
- `pytest tests -q --tb=line`

Observed result:

- `174 passed`
- `1 skipped`
- `2 warnings`

This baseline is useful as the starting point for any follow-up work described in the feature plan.
