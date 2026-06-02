# Feature Delivery Plan

This plan is written so another agent or contributor can pick it up independently, understand the intended order of work, and execute it without relying on local session context.

## Objective

Add the next set of user-facing features in a sequence that builds on the current architecture without destabilizing the existing CLI, retrieval, benchmarking, and GUI workflows.

## Current State Summary

CodeSensei already provides:

- code indexing and semantic retrieval
- CLI ask/chat/docs/tests/refactor workflows
- hybrid LLM fallback behavior
- a desktop GUI
- runtime metrics and retrieval benchmark reporting in CI

The next features should improve responsiveness, project freshness, and editor integration.

## Delivery Principles

1. Preserve existing CLI and GUI behavior by adding features incrementally.
2. Ship each feature with tests and documentation before moving to the next one.
3. Prefer features that reuse current retrieval, indexing, and assistant abstractions.
4. Keep benchmark and CI coverage aligned with any retrieval-facing changes.

## Recommended Feature Order

### Milestone 1 — Response Streaming

#### Goal

Let users see long-running answers progressively instead of waiting for the full response.

#### Why this goes first

- It improves perceived performance immediately.
- It affects the user experience more than the storage model.
- It can be added without changing the indexing pipeline.

#### Expected touch points

- `src/code_sensei/assistant/_base.py`
- `src/code_sensei/assistant/qa.py`
- `src/code_sensei/assistant/doc_generator.py`
- `src/code_sensei/assistant/refactor.py`
- `src/code_sensei/assistant/test_generator.py`
- `src/code_sensei/cli.py`
- `src/code_sensei/gui/app.py`
- relevant tests under `tests/`

#### Required work

1. Define a single streaming contract for assistant responses.
2. Add CLI support that renders partial output cleanly.
3. Add GUI support that appends partial output without freezing the interface.
4. Preserve the existing non-streaming path for providers or commands that cannot stream.
5. Update docs and examples to show both streaming and non-streaming usage.

#### Acceptance criteria

- streaming can be enabled for supported commands
- non-streaming behavior still works
- tests cover streamed and non-streamed outputs
- docs explain when streaming is available and when fallback occurs

## Milestone 2 — Watch-Driven Incremental Reindexing

### Goal

Keep project indexes fresher with less manual reindexing effort.

### Why this follows streaming

- the repository already has watcher foundations
- fresher indexes improve answer quality across both CLI and GUI
- it is smaller and lower risk than a new external integration

### Expected touch points

- `src/code_sensei/indexer/watcher.py`
- `src/code_sensei/indexer/file_loader.py`
- `src/code_sensei/retrieval/vector_store.py`
- `src/code_sensei/cli.py`
- `src/code_sensei/gui/app.py`
- relevant tests under `tests/`

### Required work

1. Confirm whether current watcher behavior is full reindex or partial refresh.
2. Design file-level update and delete handling for the index.
3. Surface index refresh state in both CLI and GUI.
4. Ensure ignored files and benchmark artifacts stay excluded.
5. Add regression tests for file add, file modify, and file delete events.

### Acceptance criteria

- modified files can be refreshed without forcing a full rebuild in the common path
- deleted files are removed from retrieval results
- watcher-triggered refresh state is visible to the user
- tests cover incremental update scenarios

## Milestone 3 — Workspace and Batch Operations

### Goal

Reduce repetitive manual setup for users who work across multiple repositories or repeated prompts.

### Why this is the third step

- it builds on stable indexing and response behavior
- it creates reusable workflows before investing in external integrations

### Expected touch points

- `src/code_sensei/cli.py`
- `src/code_sensei/memory/conversation.py`
- configuration handling under `config/settings.py`
- possible new workspace/profile module under `src/code_sensei/`
- relevant tests under `tests/`

### Required work

1. Define a workspace profile format for saved project paths and command defaults.
2. Add batch question or batch benchmark execution for repeatable runs.
3. Add import/export support for workspace definitions if needed.
4. Document the file format and expected user workflow.

### Acceptance criteria

- users can save and reuse project-specific defaults
- repeated question or benchmark workflows can run without manual repetition
- docs describe how workspace state is created and reused

## Milestone 4 — Editor Integration

### Goal

Expose core CodeSensei workflows inside a developer editor, starting with VS Code.

### Why this is last

- it depends on stable streaming and indexing behavior
- it introduces a separate delivery surface and packaging needs
- it is easiest to scope once the local APIs and workflows settle

### Required work

1. Define the smallest supported editor feature set.
2. Decide whether the extension shells out to the CLI or talks to a service layer.
3. Implement project selection, ask flow, and result display first.
4. Defer advanced editing or refactor actions until the read-only experience is stable.

### Acceptance criteria

- a user can run a project-scoped ask workflow from VS Code
- setup steps are documented
- integration failure states are actionable

## Cross-Cutting Work for Every Milestone

For each milestone, the implementing agent should also:

1. update `README.md` and any relevant docs in `/docs`
2. add or update tests in `/tests`
3. run:
   - `ruff check src tests`
   - `black --check src tests`
   - `mypy src`
   - `pytest tests -q --tb=line`
4. update benchmark coverage when retrieval behavior changes
5. record user-visible changes in `docs/CHANGELOG.md`

## Suggested Execution Strategy

1. Deliver one milestone per pull request.
2. Keep feature flags or graceful fallbacks where rollout risk exists.
3. Avoid bundling editor integration with retrieval or indexing rewrites.
4. Re-baseline retrieval benchmarks only after intentional retrieval improvements are validated.

## Open Questions to Resolve Before Implementation

1. Which commands should support streaming first: only `ask`, or `docs` and `refactor` as well?
2. Should watcher-driven refresh run automatically in the GUI by default, or remain opt-in?
3. Is batch processing focused on repeated prompts, repeated benchmarks, or both?
4. Should VS Code integration stay read-only at first, or include file actions from the start?

## Handoff Checklist for the Next Agent

Before starting implementation, the next agent should:

- read `docs/RECENT_CHANGES.md`
- read `README.md`
- inspect the current assistant, indexer, and GUI touch points for the milestone being worked on
- run the repository validation commands
- confirm whether any benchmark or CI baselines need to move as part of the change
