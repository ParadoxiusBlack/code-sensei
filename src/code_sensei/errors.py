"""
errors.py
---------
Typed exceptions for CodeSensei with user-actionable messages.

All public exception classes inherit from ``CodeSenseiError`` so callers
can catch the whole family with a single ``except CodeSenseiError``.
"""

from __future__ import annotations


class CodeSenseiError(Exception):
    """Base exception for all CodeSensei errors."""


class OllamaConnectionError(CodeSenseiError):
    """Ollama server is not reachable (connection refused / timed-out)."""

    hint = "Start Ollama with:  ollama serve"

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        super().__init__(
            f"Cannot connect to Ollama at {base_url}. " "Make sure the Ollama server is running."
        )
        self.base_url = base_url


class ModelNotFoundError(CodeSenseiError):
    """The requested model has not been pulled to the local Ollama instance."""

    def __init__(self, model: str) -> None:
        super().__init__(f"Model '{model}' not found in Ollama.")
        self.model = model
        self.hint = f"Pull the model with:  ollama pull {model}"


class EmbeddingModelError(CodeSenseiError):
    """The embedding model cannot be initialised."""

    def __init__(self, model: str, reason: str) -> None:
        super().__init__(f"Embedding model '{model}' is not available: {reason}")
        self.model = model
        self.reason = reason


class VectorStoreDimensionError(CodeSenseiError):
    """ChromaDB collection contains vectors of a different dimension."""

    hint = (
        "The stored embeddings were created with a different model. "
        "Re-index the project:  code-sensei index <project-dir>"
    )

    def __init__(
        self, collection: str, stored_dim: int | None = None, new_dim: int | None = None
    ) -> None:
        detail = (
            f" (stored {stored_dim}-d, current model produces {new_dim}-d)"
            if stored_dim and new_dim
            else ""
        )
        super().__init__(f"Embedding dimension mismatch in collection '{collection}'{detail}.")
        self.collection = collection
