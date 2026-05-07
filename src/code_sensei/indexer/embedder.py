"""
indexer/embedder.py
-------------------
Generates vector embeddings for ``Chunk`` objects using the configured
embedding provider (OpenAI by default).

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
    from config.settings import EMBEDDING_MODEL, EMBEDDING_PROVIDER
except ImportError:
    EMBEDDING_MODEL = "text-embedding-3-large"
    EMBEDDING_PROVIDER = "openai"

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
        Embedding provider — ``"openai"`` or ``"azure_openai"``
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
        """Instantiate the embedding model from the configured provider."""
        try:
            if self.provider == "azure_openai":
                from langchain_openai import AzureOpenAIEmbeddings

                return AzureOpenAIEmbeddings(model=self.model)
            else:
                from langchain_openai import OpenAIEmbeddings

                return OpenAIEmbeddings(model=self.model)
        except Exception as exc:
            logger.warning(
                "Could not load embedding model (%s). "
                "Embedder will return zero vectors until a valid API key is set. "
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
