"""
tests/test_chunker.py
---------------------
Unit tests for code_sensei.indexer.chunker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from code_sensei.indexer.chunker import Chunk, Chunker, _FallbackSplitter, _make_chunk_id
from code_sensei.indexer.file_loader import SourceFile


# ---------------------------------------------------------------------------
# _make_chunk_id
# ---------------------------------------------------------------------------


class TestMakeChunkId:
    def test_deterministic(self):
        assert _make_chunk_id("/src/foo.py", 0) == _make_chunk_id("/src/foo.py", 0)

    def test_different_for_different_offsets(self):
        assert _make_chunk_id("/src/foo.py", 0) != _make_chunk_id("/src/foo.py", 100)

    def test_different_for_different_paths(self):
        assert _make_chunk_id("/src/foo.py", 0) != _make_chunk_id("/src/bar.py", 0)

    def test_length_is_16(self):
        assert len(_make_chunk_id("/src/foo.py", 0)) == 16


# ---------------------------------------------------------------------------
# _FallbackSplitter
# ---------------------------------------------------------------------------


class TestFallbackSplitter:
    def test_splits_text_into_chunks(self):
        splitter = _FallbackSplitter(chunk_size=10, chunk_overlap=2)
        result = splitter.split_text("0123456789abcdefghij")
        assert len(result) > 1

    def test_chunk_size_respected(self):
        splitter = _FallbackSplitter(chunk_size=5, chunk_overlap=0)
        result = splitter.split_text("12345" * 4)
        assert all(len(c) <= 5 for c in result)

    def test_empty_input(self):
        splitter = _FallbackSplitter(chunk_size=10, chunk_overlap=2)
        result = splitter.split_text("")
        assert result == []

    def test_overlap_creates_more_chunks(self):
        text = "a" * 100
        no_overlap = _FallbackSplitter(chunk_size=20, chunk_overlap=0).split_text(text)
        with_overlap = _FallbackSplitter(chunk_size=20, chunk_overlap=10).split_text(text)
        assert len(with_overlap) >= len(no_overlap)


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------


def _make_source_file(tmp_path: Path, name: str = "sample.py", content: str = "") -> SourceFile:
    path = tmp_path / name
    path.write_text(content)
    return SourceFile(path=path, content=content, language="python")


class TestChunker:
    def test_returns_list_of_chunks(self, tmp_path):
        content = "def foo():\n    pass\n" * 30
        sf = _make_source_file(tmp_path, content=content)
        chunker = Chunker(chunk_size=50, chunk_overlap=5)
        chunks = chunker.chunk_file(sf)
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_content_is_non_empty(self, tmp_path):
        content = "x = 1\n" * 50
        sf = _make_source_file(tmp_path, content=content)
        chunker = Chunker(chunk_size=50, chunk_overlap=5)
        chunks = chunker.chunk_file(sf)
        assert all(c.content.strip() for c in chunks)

    def test_chunk_ids_are_unique(self, tmp_path):
        content = "y = 2\n" * 100
        sf = _make_source_file(tmp_path, content=content)
        chunker = Chunker(chunk_size=50, chunk_overlap=5)
        chunks = chunker.chunk_file(sf)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_source_path_is_preserved(self, tmp_path):
        content = "z = 3\n" * 20
        sf = _make_source_file(tmp_path, content=content)
        chunker = Chunker(chunk_size=30, chunk_overlap=5)
        chunks = chunker.chunk_file(sf)
        for c in chunks:
            assert c.source_path == str(sf.path)

    def test_language_is_preserved(self, tmp_path):
        content = "pass\n" * 20
        sf = _make_source_file(tmp_path, content=content)
        chunker = Chunker(chunk_size=30, chunk_overlap=5)
        chunks = chunker.chunk_file(sf)
        for c in chunks:
            assert c.language == "python"

    def test_chunk_files_flattens_results(self, tmp_path):
        files = [
            _make_source_file(tmp_path, name=f"f{i}.py", content="x=1\n" * 20)
            for i in range(3)
        ]
        chunker = Chunker(chunk_size=30, chunk_overlap=5)
        all_chunks = chunker.chunk_files(files)
        assert len(all_chunks) > 3

    def test_short_content_produces_single_chunk(self, tmp_path):
        content = "x = 1\n"
        sf = _make_source_file(tmp_path, content=content)
        chunker = Chunker(chunk_size=1000, chunk_overlap=0)
        chunks = chunker.chunk_file(sf)
        assert len(chunks) == 1
        assert content.strip() in chunks[0].content

    def test_metadata_contains_expected_keys(self, tmp_path):
        content = "a = 1\n" * 10
        sf = _make_source_file(tmp_path, content=content)
        chunker = Chunker(chunk_size=20, chunk_overlap=2)
        chunks = chunker.chunk_file(sf)
        for c in chunks:
            assert "language" in c.metadata
            assert "chunk_index" in c.metadata

    def test_char_count_property(self, tmp_path):
        content = "b = 2\n" * 10
        sf = _make_source_file(tmp_path, content=content)
        chunker = Chunker(chunk_size=20, chunk_overlap=2)
        chunks = chunker.chunk_file(sf)
        for c in chunks:
            assert c.char_count == len(c.content)
