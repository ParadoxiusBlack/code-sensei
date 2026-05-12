"""
indexer/embedder.py
-------------------
Generates vector embeddings for ``Chunk`` objects using the configured
embedding provider (Ollama by default).

Design notes
~~~~~~~~~~~~
* Embedding calls are batched to stay within provider rate limits.
* Results are returned as ``EmbeddedChunk`` objects — a ``Chunk`` plus a
  ``list[float]`` embedding vector — so the caller can persist them to the
  vector store without needing to re-fetch metadata.
* The ``Embedder`` is intentionally provider-agnostic: swapping to Anthropic
  or a local sentence-transformer requires only a different ``_build_model``
  implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from .chunker import Chunk

try:
    from config.settings import EMBEDDING_MODEL, EMBEDDING_PROVIDER, OLLAMA_BASE_URL
except ImportError:
    EMBEDDING_MODEL = "nomic-embed-text"
    EMBEDDING_PROVIDER = "ollama"
    OLLAMA_BASE_URL = "http://localhost:11434"

try:
    from ..errors import EmbeddingModelError, ModelNotFoundError, OllamaConnectionError
except ImportError:
    EmbeddingModelError = Exception  # type: ignore[misc,assignment]
    ModelNotFoundError = Exception  # type: ignore[misc,assignment]
    OllamaConnectionError = Exception  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE = 100


@dataclass
class EmbeddedChunk:
    """A ``Chunk`` paired with its embedding vector."""

    chunk: Chunk
    embedding: list[float]

    @property
    def chunk_id(self) -> str:
        return self.chunk.chunk_id


class Embedder:
    """
    Embeds ``Chunk`` objects using a configured embedding model.

    Parameters
    ----------
    model:
        Embedding model name (default: ``EMBEDDING_MODEL`` from settings).
    provider:
        Embedding provider — ``"ollama"``, ``"openai"`` or ``"azure_openai"``
        (default: ``EMBEDDING_PROVIDER`` from settings).
    batch_size:
        Number of chunks to embed per API call.
    """

    def __init__(
        self,
        model: str | None = None,
        provider: str | None = None,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> None:
        self.model = model or EMBEDDING_MODEL
        self.provider = provider or EMBEDDING_PROVIDER
        self.batch_size = batch_size
        #: Human-readable explanation of why embeddings are unavailable (None = OK).
        self.embed_init_error: str | None = None
        self._embedding_model = self._build_model()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_chunks(self, chunks: Sequence[Chunk]) -> list[EmbeddedChunk]:
        """Return ``EmbeddedChunk`` objects for every input ``Chunk``."""
        results: list[EmbeddedChunk] = []
        for i in range(0, len(chunks), self.batch_size):
            batch = list(chunks[i : i + self.batch_size])
            texts = [c.content for c in batch]
            vectors = self._embed_texts(texts)
            for chunk, vector in zip(batch, vectors):
                results.append(EmbeddedChunk(chunk=chunk, embedding=vector))
        return results

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (used at retrieval time)."""
        vectors = self._embed_texts([text])
        return vectors[0] if vectors else []

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_model(self):  # type: ignore[return]
        """Instantiate the embedding model from the configured provider.

        On failure sets ``self.embed_init_error`` with an actionable message.
        """
        try:
            if self.provider == "ollama":
                from langchain_ollama import OllamaEmbeddings

                return OllamaEmbeddings(model=self.model, base_url=OLLAMA_BASE_URL)
            if self.provider == "azure_openai":
                from langchain_openai import AzureOpenAIEmbeddings

                return AzureOpenAIEmbeddings(model=self.model)
            if self.provider == "openai":
                from langchain_openai import OpenAIEmbeddings

                return OpenAIEmbeddings(model=self.model)

            raise ValueError(f"Unsupported embedding provider: {self.provider}")
        except Exception as exc:
            exc_lower = str(exc).lower()
            if (
                "connection refused" in exc_lower
                or "connect error" in exc_lower
                or "connectionerror" in exc_lower
                or "cannot connect" in exc_lower
            ):
                conn_err = OllamaConnectionError(OLLAMA_BASE_URL)
                self.embed_init_error = (
                    f"Embedding model unavailable — Ollama is not running. "
                    f"Hint: {conn_err.hint}"
                )
            elif "not found" in exc_lower or "404" in exc_lower:
                model_err = ModelNotFoundError(self.model)
                self.embed_init_error = f"{model_err}  Hint: {model_err.hint}"
            else:
                self.embed_init_error = (
                    f"Could not load embedding model '{self.model}' "
                    f"({self.provider}): {exc}"
                )
            logger.warning(
                "Could not load embedding model (%s). "
                "Embedder will return zero vectors until the provider is available. "
                "Error: %s",
                self.model,
                exc,
            )
            return None

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Call the underlying model to embed a list of text strings."""
        if self._embedding_model is None:
            # Return zero vectors when the model is unavailable (e.g. no API key).
            logger.debug("No embedding model available; returning zero vectors.")
            return [[0.0] * 1536 for _ in texts]
        try:
            return self._embedding_model.embed_documents(texts)
        except Exception as exc:
            logger.error("Embedding failed: %s", exc)
            return [[0.0] * 1536 for _ in texts]
