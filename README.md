# CodeSensei 🧑‍💻

**Local Codebase LLM Assistant** — embeddings + retrieval-augmented generation (RAG)
to understand your codebase and provide intelligent developer assistance.

---

## Features

| Capability | Description |
|---|---|
| **Code Q&A** | Ask "What does this module do?" or "Where is X used?" |
| **Test Generation** | Auto-generate unit tests, integration tests, and mock stubs |
| **Refactor Suggestions** | Identify code smells and propose concrete improvements |
| **Documentation** | Generate docstrings, READMEs, and architecture overviews |
| **Embeddings Search** | Vector search over indexed code chunks (ChromaDB) |
| **Conversation Memory** | Multi-turn reasoning with SQLite-backed session history |
| **File Watcher** | Auto-reindex on file changes via `watchdog` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        CLI (click + rich)                │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────▼──────────────┐
          │        Assistant Layer       │
          │  CodeQA · TestGen · Refactor │
          │  DocGen · ConversationMemory │
          └──────────────┬──────────────┘
                         │ retrieves
          ┌──────────────▼──────────────┐
          │       Retrieval Layer        │
          │   Retriever · VectorStore    │
          │        (ChromaDB)            │
          └──────────────┬──────────────┘
                         │ indexed by
          ┌──────────────▼──────────────┐
          │        Indexer Layer         │
          │  FileLoader · Chunker        │
          │  Embedder · CodebaseWatcher  │
          └─────────────────────────────┘
          ┌─────────────────────────────┐
          │       Cache Layer            │
          │   SQLiteCache (key-value)    │
          └─────────────────────────────┘
```

---

## Quick Start

### 1 — Prerequisites

- Python ≥ 3.10
- Ollama installed (for fully local/offline usage)
- Optional: OpenAI (or Azure OpenAI / Anthropic) API key

### 2 — Install

```bash
# Clone the repo
git clone https://github.com/ParadoxiusBlack/code-sensei.git
cd code-sensei

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install the package and dependencies
pip install -e ".[dev]"
```

### 3 — Configure

```bash
cp .env.example .env
# Local-first defaults already use Ollama for chat + embeddings.
# Optional: add OPENAI_API_KEY for cloud fallback.
```

### 4 — Pull local models

```bash
ollama pull mistral
ollama pull nomic-embed-text
```

### 5 — Index your codebase

```bash
code-sensei index /path/to/your/project
```

### 6 — Ask questions

```bash
code-sensei ask "What does the FileLoader class do?" -p /path/to/your/project
```

### 7 — Interactive chat

```bash
code-sensei chat -p /path/to/your/project
```

---

## CLI Reference

```
Usage: code-sensei [OPTIONS] COMMAND [ARGS]...

Commands:
  index     Index (or re-index) a codebase directory.
  ask       Ask a natural-language question about the indexed codebase.
  benchmark-retrieval  Run retrieval quality benchmarks from a dataset.
  tests     Generate unit / integration tests for a file or module.
  refactor  Analyse code for refactoring opportunities.
  docs      Generate documentation for a file, module, or the project.
  chat      Start an interactive multi-turn chat session.
  status    Show index statistics for the project.
  watch     Watch a codebase directory and auto-reindex on file changes.
  gui       Launch desktop GUI front-end.
```

### Examples

```bash
# Generate pytest tests for a module
code-sensei tests src/my_module.py --framework pytest --output tests/test_my_module.py

# Suggest refactoring improvements
code-sensei refactor "authentication module" --language python

# Generate a README
code-sensei docs . --type readme --output README_generated.md

# Watch for changes and auto-reindex
code-sensei watch /path/to/project

# Run retrieval benchmark dataset
code-sensei benchmark-retrieval -p . -d benchmarks/retrieval/code_sensei_smoke.json

# Launch desktop GUI (Phase 4)
code-sensei gui -p /path/to/project
```

### Metrics Output

The CLI now exposes lightweight observability metrics for core workflows.

`ask` prints:
- total query time
- retrieval time
- generation time
- embedding time
- vector query time
- average result score

`index` prints:
- total indexing time
- files/sec
- chunks/sec
- average chunks/file

Example:

```bash
code-sensei ask "Where is file loading implemented?" -p . --no-stream
code-sensei index .
```

### Retrieval Benchmarks

Benchmark datasets live under `benchmarks/retrieval/` and are JSON arrays with this shape:

```json
[
  {
    "query": "Which method converts Chroma cosine distance into a 0-to-1 similarity score?",
    "expected_sources": ["src/code_sensei/retrieval/retriever.py"],
    "top_k": 5
  }
]
```

Run a benchmark and save the machine-readable summary:

```bash
code-sensei benchmark-retrieval \
  -p . \
  -d benchmarks/retrieval/code_sensei_smoke.json \
  --output-json retrieval-benchmark-summary.json
```

The benchmark summary includes:
- average latency
- Recall@k
- MRR
- hit rate
- per-query case details

### CI Benchmark Reporting

GitHub Actions now includes a retrieval benchmark job that:
- provisions Ollama
- pulls `nomic-embed-text`
- indexes the repository
- runs the smoke retrieval benchmark
- compares the summary to `benchmarks/retrieval/ci_baseline_summary.json`
- publishes a delta report artifact and step summary

The delta report also supports soft, non-blocking regression warnings for:
- latency regressions above a configured threshold
- retrieval quality drops beyond a configured threshold

---

## GUI (Phase 4)

CodeSensei now includes a PyQt6 desktop interface:

- Ask/answer pane for natural-language codebase questions.
- Source list from retrieval hits.
- Code viewer for selected source snippets.
- Select Project button to switch to any project folder on your machine.


Install GUI dependency:

```bash
pip install PyQt6
```

Launch:

```bash
code-sensei gui -p /path/to/project
```

Windows one-click launch:

- Double-click [Run CodeSensei GUI.bat](Run%20CodeSensei%20GUI.bat) in the project root.
- The launcher auto-uses `.venv\\Scripts\\python(.exe|pythonw.exe)` and opens GUI for this project.
- If the GUI does not appear, run [Run CodeSensei GUI (Debug).bat](Run%20CodeSensei%20GUI%20(Debug).bat) to see startup errors.

Optional flags:

- `--top-k 12` tune retrieval breadth.
- `--no-llm` start in retrieval-only mode.

Standalone Windows `.exe` build:

```powershell
# From project root
powershell -ExecutionPolicy Bypass -File scripts/build_gui_exe.ps1
```

Build output:

- Preferred (one-file): `dist/CodeSenseiGUI.exe`
- Fallback (one-dir, if toolchain chooses it): `dist/CodeSenseiGUI/CodeSenseiGUI.exe`

Run the built app:

```powershell
./dist/CodeSenseiGUI.exe
```

Inside the GUI:

- Click **Select Project...** to choose any folder in File Explorer.
- The selected project is automatically indexed in the background.
- The active project and indexed chunk count are shown at the top.
- Use the **Reindex** button any time to refresh embeddings.
- Use the **Project Files** tab to browse folder structure, open files, edit text files, and save changes.

If you prefer CLI indexing first, you can still run:

```bash
code-sensei index /path/to/project
```

---

## Project Structure

```
code-sensei/
├── src/
│   └── code_sensei/
│       ├── cli.py               # CLI entry point (click + rich)
│       ├── indexer/
│       │   ├── file_loader.py   # Walk & load source files
│       │   ├── chunker.py       # Chunk files for embedding
│       │   ├── embedder.py      # Generate embeddings (Ollama/OpenAI/Azure)
│       │   └── watcher.py       # File-system watcher (watchdog)
│       ├── retrieval/
│       │   ├── vector_store.py  # ChromaDB wrapper
│       │   └── retriever.py     # Semantic search + ranking
│       ├── assistant/
│       │   ├── qa.py            # Code Q&A (RAG)
│       │   ├── test_generator.py
│       │   ├── refactor.py
│       │   └── doc_generator.py
│       ├── gui/
│       │   └── app.py           # PyQt6 desktop interface
│       ├── memory/
│       │   └── conversation.py  # Multi-turn memory
│       └── cache/
│           └── sqlite_cache.py  # SQLite key-value cache
├── tests/                       # pytest test suite
├── config/
│   └── settings.py              # Centralised configuration
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=code_sensei --cov-report=term-missing

# Lint
ruff check src/ tests/

# Format
black src/ tests/

# Run retrieval smoke benchmark
code-sensei benchmark-retrieval -p . -d benchmarks/retrieval/code_sensei_smoke.json
```

## Additional Documentation

- [docs/RECENT_CHANGES.md](docs/RECENT_CHANGES.md) — summary of the latest retrieval, CI, and observability changes plus the rationale behind them
- [docs/FEATURE_PLAN.md](docs/FEATURE_PLAN.md) — execution-ready feature roadmap for the next delivery milestones
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — chronological change history

---

## Roadmap

- [x] Phase 1 — Scaffold: project structure, indexer pipeline, vector store
- [x] Phase 2 — Retrieval: improve ranking, add hybrid BM25 + vector search
- [x] Phase 3 — Features: refine prompts, advanced error handling, performance tuning
- [x] Phase 4 — GUI: PyQt6 front-end with integrated code viewer
- [x] Phase 5 — Benchmarking, observability metrics, and CI delta reporting
- [ ] Phase 6 — Streaming responses, fresher indexing workflows, and editor-facing integrations

For the detailed follow-up plan, see [docs/FEATURE_PLAN.md](docs/FEATURE_PLAN.md).

---

## License

MIT © ParadoxiusBlack
