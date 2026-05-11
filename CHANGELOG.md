# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
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
