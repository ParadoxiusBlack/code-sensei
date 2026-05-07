"""
indexer/chunker.py
------------------
Splits ``SourceFile`` content into overlapping ``Chunk`` objects suitable
for embedding.  Uses LangChain's ``RecursiveCharacterTextSplitter`` for
language-aware splitting, with a plain character splitter as fallback.

Design notes
~~~~~~~~~~~~
* Each ``Chunk`` carries a stable ``chunk_id`` derived from its source
  file path + character offset so the vector store can deduplicate/update
  individual chunks without re-indexing the entire codebase.
* Token-budget awareness: ``max_tokens`` (optional) lets callers cap
  chunk size in tokens rather than characters.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Sequence

try:
    from config.settings import CHUNK_OVERLAP, CHUNK_SIZE
except ImportError:
    CHUNK_SIZE = 512
    CHUNK_OVERLAP = 64

from .file_loader import SourceFile

logger = logging.getLogger(__name__)

# Mapping from language string to LangChain Language enum value.
_LANGCHAIN_LANGUAGE_MAP: dict[str, str] = {
    "python": "python",
    "javascript": "js",
    "typescript": "ts",
    "java": "java",
    "go": "go",
    "ruby": "ruby",
    "rust": "rust",
    "cpp": "cpp",
    "c": "c",
    "csharp": "csharp",
    "scala": "scala",
    "swift": "swift",
}


@dataclass
class Chunk:
    """A single text chunk extracted from a source file."""

    chunk_id: str
    content: str
    source_path: str
    language: str
    start_char: int
    end_char: int
    metadata: dict = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.content)


def _make_chunk_id(source_path: str, start_char: int) -> str:
    """Deterministic chunk ID from path + offset."""
    raw = f"{source_path}:{start_char}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class Chunker:
    """
    Splits ``SourceFile`` objects into ``Chunk`` objects.

    Parameters
    ----------
    chunk_size:
        Target character count per chunk (default: ``CHUNK_SIZE`` from settings).
    chunk_overlap:
        Character overlap between consecutive chunks (default: ``CHUNK_OVERLAP``).
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self.chunk_size = chunk_size if chunk_size is not None else CHUNK_SIZE
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else CHUNK_OVERLAP

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk_file(self, source_file: SourceFile) -> list[Chunk]:
        """Return a list of ``Chunk`` objects for a single ``SourceFile``."""
        splitter = self._build_splitter(source_file.language)
        texts = splitter.split_text(source_file.content)
        return self._texts_to_chunks(texts, source_file)

    def chunk_files(self, source_files: Sequence[SourceFile]) -> list[Chunk]:
        """Chunk multiple ``SourceFile`` objects and return a flat list."""
        chunks: list[Chunk] = []
        for sf in source_files:
            chunks.extend(self.chunk_file(sf))
        return chunks

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_splitter(self, language: str):  # type: ignore[return]
        """Build a LangChain text splitter, falling back to plain character split."""
        try:
            from langchain.text_splitter import (
                Language,
                RecursiveCharacterTextSplitter,
            )

            lc_lang = _LANGCHAIN_LANGUAGE_MAP.get(language)
            if lc_lang:
                return RecursiveCharacterTextSplitter.from_language(
                    language=Language(lc_lang),
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                )
            return RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
        except Exception:  # pragma: no cover — langchain not installed in unit tests
            return _FallbackSplitter(
                chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
            )

    def _texts_to_chunks(
        self, texts: list[str], source_file: SourceFile
    ) -> list[Chunk]:
        """Convert raw text segments back to ``Chunk`` objects with offsets."""
        chunks: list[Chunk] = []
        cursor = 0
        content = source_file.content

        for text in texts:
            # Find the actual position of this text segment in the original content.
            start = content.find(text, cursor)
            if start == -1:
                # Fallback: keep cursor advancing linearly.
                start = cursor
            end = start + len(text)

            chunk_id = _make_chunk_id(str(source_file.path), start)

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    content=text,
                    source_path=str(source_file.path),
                    language=source_file.language,
                    start_char=start,
                    end_char=end,
                    metadata={
                        **source_file.metadata,
                        "language": source_file.language,
                        "chunk_index": len(chunks),
                        "total_chars": len(content),
                    },
                )
            )
            cursor = max(cursor + 1, end - self.chunk_overlap)

        return chunks


# ---------------------------------------------------------------------------
# Fallback splitter (used when LangChain is unavailable, e.g. in tests)
# ---------------------------------------------------------------------------


class _FallbackSplitter:
    """Simple character-based splitter that does not depend on LangChain."""

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> list[str]:
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            start += self.chunk_size - self.chunk_overlap
        return chunks
