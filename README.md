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
- An OpenAI (or Azure OpenAI / Anthropic) API key

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
# Edit .env and set OPENAI_API_KEY (and any other values)
```

### 4 — Index your codebase

```bash
code-sensei index /path/to/your/project
```

### 5 — Ask questions

```bash
code-sensei ask "What does the FileLoader class do?" -p /path/to/your/project
```

### 6 — Interactive chat

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
  tests     Generate unit / integration tests for a file or module.
  refactor  Analyse code for refactoring opportunities.
  docs      Generate documentation for a file, module, or the project.
  chat      Start an interactive multi-turn chat session.
  status    Show index statistics for the project.
  watch     Watch a codebase directory and auto-reindex on file changes.
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
│       │   ├── embedder.py      # Generate embeddings (OpenAI)
│       │   └── watcher.py       # File-system watcher (watchdog)
│       ├── retrieval/
│       │   ├── vector_store.py  # ChromaDB wrapper
│       │   └── retriever.py     # Semantic search + ranking
│       ├── assistant/
│       │   ├── qa.py            # Code Q&A (RAG)
│       │   ├── test_generator.py
│       │   ├── refactor.py
│       │   └── doc_generator.py
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
```

---

## Roadmap

- [x] Phase 1 — Scaffold: project structure, indexer pipeline, vector store
- [ ] Phase 2 — Retrieval: improve ranking, add hybrid BM25 + vector search
- [ ] Phase 3 — Features: refine prompts, add streaming responses
- [ ] Phase 4 — GUI: PyQt6 or Electron front-end, code viewer

---

## License

MIT © ParadoxiusBlack
