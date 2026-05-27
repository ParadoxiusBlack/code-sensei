"""
retrieval/vector_store.py
-------------------------
Abstraction layer over ChromaDB (the default local vector store).

Design notes
~~~~~~~~~~~~
* A thin wrapper so the rest of the codebase does not import ChromaDB
  directly — swapping to Pinecone/Weaviate only requires a new
  ``VectorStore`` implementation.
* Chunks are upserted by ``chunk_id`` so repeated indexing is idempotent.
* The collection name is derived from the project root name, allowing
  multiple projects to share the same ChromaDB instance.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

try:
    from config.settings import CHROMA_PERSIST_DIR, EMBEDDING_MODEL, EMBEDDING_PROVIDER
except ImportError:
    CHROMA_PERSIST_DIR = Path(".chroma")
    EMBEDDING_MODEL = "nomic-embed-text"
    EMBEDDING_PROVIDER = "ollama"

from ..indexer.embedder import EmbeddedChunk

logger = logging.getLogger(__name__)

_DEFAULT_COLLECTION = "code_sensei_default"
ChromaClient = Any
ChromaCollection = Any


class VectorStore:
    """
    ChromaDB-backed vector store for code chunks.

    Parameters
    ----------
    collection_name:
        Name of the ChromaDB collection.
    persist_dir:
        Directory where ChromaDB persists its data.
    """

    def __init__(
        self,
        collection_name: str = _DEFAULT_COLLECTION,
        persist_dir: str | Path | None = None,
    ) -> None:
        self.collection_name = collection_name
        self.persist_dir = Path(persist_dir or CHROMA_PERSIST_DIR).resolve()
        self._client: ChromaClient | None = None
        self._collection: ChromaCollection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Open (or create) the ChromaDB collection."""
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(self.persist_dir))
            self._client = client
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                "VectorStore connected — collection '%s' at %s",
                self.collection_name,
                self.persist_dir,
            )
        except ImportError:
            logger.error(
                "chromadb is not installed. Run `pip install chromadb` to enable "
                "vector-store functionality."
            )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert(self, embedded_chunks: Sequence[EmbeddedChunk]) -> None:
        """Insert or update embedded chunks in the collection."""
        if self._collection is None:
            raise RuntimeError("VectorStore is not connected. Call connect() first.")

        ids = [ec.chunk_id for ec in embedded_chunks]
        embeddings = [ec.embedding for ec in embedded_chunks]
        documents = [ec.chunk.content for ec in embedded_chunks]
        metadatas = [
            {
                **ec.chunk.metadata,
                "source_path": ec.chunk.source_path,
                "language": ec.chunk.language,
                "start_char": ec.chunk.start_char,
                "end_char": ec.chunk.end_char,
            }
            for ec in embedded_chunks
        ]

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.debug("Upserted %d chunks.", len(embedded_chunks))

    def delete_by_source(self, source_path: str) -> None:
        """Remove all chunks that originate from a given source file."""
        if self._collection is None:
            raise RuntimeError("VectorStore is not connected.")
        self._collection.delete(where={"source_path": source_path})
        logger.debug("Deleted chunks from: %s", source_path)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict | None = None,
    ) -> list[dict]:
        """
        Return the ``n_results`` most similar chunks.

        Returns a list of dicts with keys:
        ``id``, ``document``, ``metadata``, ``distance``.
        """
        if self._collection is None:
            raise RuntimeError("VectorStore is not connected.")

        kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        result = self._collection.query(**kwargs)
        hits: list[dict] = []
        for i, doc_id in enumerate(result["ids"][0]):
            hits.append(
                {
                    "id": doc_id,
                    "document": result["documents"][0][i],
                    "metadata": result["metadatas"][0][i],
                    "distance": result["distances"][0][i],
                }
            )
        return hits

    def count(self) -> int:
        """Return the total number of chunks in the collection."""
        if self._collection is None:
            return 0
        return self._collection.count()

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> VectorStore:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        pass  # ChromaDB PersistentClient handles its own cleanup.
