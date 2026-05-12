# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added (Phase 3 — Error Handling)
- New `src/code_sensei/errors.py` with typed exception classes:
  - `OllamaConnectionError` — Ollama server not reachable; carries `ollama serve` hint.
  - `ModelNotFoundError` — Ollama model not pulled; carries `ollama pull <model>` hint.
  - `EmbeddingModelError` — Embedding provider/model unavailable.
  - `VectorStoreDimensionError` — ChromaDB dimension mismatch; carries re-index hint.
- `_BaseAssistant.llm_init_error: str | None` — populated with an actionable message when the LLM cannot be initialised.
- `Embedder.embed_init_error: str | None` — populated when the embedding model cannot be loaded.
- CLI helper functions `_warn_panel()`, `_error_panel()`, `_check_llm_status()`, `_check_embed_status()`, `_handle_vector_store_error()` for Rich-formatted user guidance.
- All CLI commands now surface LLM / embedding / vector-store errors as Rich panels instead of Python tracebacks.
- New `tests/test_error_handling.py` covering typed exceptions, LLM diagnostics, embedder diagnostics, and CLI helpers.

### Fixed
- `index` command now catches ChromaDB dimension errors and prints an actionable re-index suggestion instead of crashing.
- `_load_pipeline()` catches vector-store connection errors and exits cleanly.

### Verification
- Full regression suite passed: `131 passed, 2 warnings` (13 new tests).

---

### Added (Phase 2 — Local Embeddings & Hybrid LLM)
- Local-first embedding configuration defaults:
  - `EMBEDDING_PROVIDER=ollama`
  - `EMBEDDING_MODEL=nomic-embed-text`
- New embedder regression tests in `tests/test_embedder.py`.
- Collection naming strategy that includes embedding provider/model to avoid Chroma dimension collisions across migrations.

### Changed
- Migrated Ollama chat integration to `langchain-ollama` (`OllamaLLM`) and added compatibility handling for string vs message responses.
- Added `langchain-ollama` dependency in both `requirements.txt` and `pyproject.toml`.
- Updated docs to reflect local/offline defaults and setup flow (`README.md`, `HYBRID_LLM_GUIDE.md`, `.env.example`).
- Updated references from `ollama.ai` to `ollama.com` in project guides.

### Fixed
- Fixed LLM invocation path where some Ollama responses were plain strings (`'str' object has no attribute 'content'`).
- Fixed index migration issue where previous OpenAI-sized vectors conflicted with Ollama embedding dimensions by namespacing collection names.

### Verification
- Full regression suite passed: `113 passed, 2 warnings`.
- End-to-end demo project check passed using local chat + local embeddings.
