"""
config/settings.py
------------------
Centralised configuration loaded from environment variables / .env file.
All modules import from here rather than calling os.getenv() directly.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (or wherever the process was started).
load_dotenv(override=False)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _get_int(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _get_float(key: str, default: float = 0.0) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# LLM provider
# ---------------------------------------------------------------------------

LLM_PROVIDER: str = _get("LLM_PROVIDER", "openai")
OPENAI_API_KEY: str = _get("OPENAI_API_KEY")
ANTHROPIC_API_KEY: str = _get("ANTHROPIC_API_KEY")

AZURE_OPENAI_API_KEY: str = _get("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT: str = _get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION: str = _get("AZURE_OPENAI_API_VERSION", "2024-02-01")
AZURE_OPENAI_DEPLOYMENT: str = _get("AZURE_OPENAI_DEPLOYMENT")

# Ollama configuration (for local LLM inference)
OLLAMA_BASE_URL: str = _get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = _get("OLLAMA_MODEL", "mistral")
OLLAMA_ENABLED: bool = _get("OLLAMA_ENABLED", "false").lower() in ("true", "1", "yes")

# Hybrid LLM mode: try Ollama first, fall back to OpenAI
HYBRID_LLM_MODE: bool = _get("HYBRID_LLM_MODE", "true").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# Embedding model
# ---------------------------------------------------------------------------

EMBEDDING_MODEL: str = _get("EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_PROVIDER: str = _get("EMBEDDING_PROVIDER", "ollama")

# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------

VECTOR_STORE_BACKEND: str = _get("VECTOR_STORE_BACKEND", "chroma")
CHROMA_PERSIST_DIR: Path = Path(_get("CHROMA_PERSIST_DIR", ".chroma"))

# ---------------------------------------------------------------------------
# Chat model
# ---------------------------------------------------------------------------

CHAT_MODEL: str = _get("CHAT_MODEL", "gpt-4o")
TEMPERATURE: float = _get_float("TEMPERATURE", 0.2)
MAX_TOKENS: int = _get_int("MAX_TOKENS", 2048)

# Retrieval-only mode: show code chunks without LLM summaries
RETRIEVAL_ONLY_MODE: bool = _get("RETRIEVAL_ONLY_MODE", "false").lower() in ("true", "1", "yes")

# Context budgeting for prompt assembly (performance + relevance tuning)
MAX_CONTEXT_CHARS: int = _get_int("MAX_CONTEXT_CHARS", 8000)
MAX_CHARS_PER_CHUNK: int = _get_int("MAX_CHARS_PER_CHUNK", 1400)
MAX_CHUNKS_PER_FILE: int = _get_int("MAX_CHUNKS_PER_FILE", 2)

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

CHUNK_SIZE: int = _get_int("CHUNK_SIZE", 512)
CHUNK_OVERLAP: int = _get_int("CHUNK_OVERLAP", 64)

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

CACHE_DB_PATH: Path = Path(_get("CACHE_DB_PATH", ".cache/code_sensei.db"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL: str = _get("LOG_LEVEL", "INFO")

# ---------------------------------------------------------------------------
# File-loader defaults
# ---------------------------------------------------------------------------

# File extensions that are considered source code and will be indexed.
DEFAULT_SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".kt",
        ".go",
        ".rb",
        ".rs",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".php",
        ".swift",
        ".scala",
        ".sh",
        ".bash",
        ".yaml",
        ".yml",
        ".toml",
        ".json",
        ".md",
        ".rst",
    }
)

# Directories to ignore when walking a codebase.
DEFAULT_IGNORE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "node_modules",
        ".venv",
        "venv",
        "env",
        ".tox",
        "dist",
        "build",
        ".eggs",
        "*.egg-info",
        ".chroma",
        ".cache",
    }
)
