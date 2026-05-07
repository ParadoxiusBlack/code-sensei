"""
tests/test_file_loader.py
-------------------------
Unit tests for code_sensei.indexer.file_loader.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from code_sensei.indexer.file_loader import FileLoader, SourceFile, _infer_language, _is_likely_binary


# ---------------------------------------------------------------------------
# _infer_language
# ---------------------------------------------------------------------------


class TestInferLanguage:
    def test_python(self, tmp_path):
        assert _infer_language(tmp_path / "foo.py") == "python"

    def test_javascript(self, tmp_path):
        assert _infer_language(tmp_path / "app.js") == "javascript"

    def test_typescript(self, tmp_path):
        assert _infer_language(tmp_path / "app.ts") == "typescript"

    def test_markdown(self, tmp_path):
        assert _infer_language(tmp_path / "README.md") == "markdown"

    def test_unknown_extension(self, tmp_path):
        assert _infer_language(tmp_path / "file.xyz") == "text"

    def test_case_insensitive(self, tmp_path):
        assert _infer_language(tmp_path / "FILE.PY") == "python"


# ---------------------------------------------------------------------------
# _is_likely_binary
# ---------------------------------------------------------------------------


class TestIsLikelyBinary:
    def test_plain_text_not_binary(self):
        assert not _is_likely_binary(b"def hello(): pass\n")

    def test_empty_not_binary(self):
        assert not _is_likely_binary(b"")

    def test_null_bytes_binary(self):
        # Many null bytes → binary
        assert _is_likely_binary(bytes(500))

    def test_png_magic_binary(self):
        png_header = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A] + [0] * 200)
        assert _is_likely_binary(png_header)


# ---------------------------------------------------------------------------
# FileLoader
# ---------------------------------------------------------------------------


class TestFileLoader:
    def test_loads_python_files(self, tmp_project: Path):
        loader = FileLoader(root=tmp_project, extensions={".py"})
        files = list(loader.load())
        names = {f.path.name for f in files}
        assert "main.py" in names
        assert "utils.py" in names

    def test_ignores_markdown_when_not_in_extensions(self, tmp_project: Path):
        loader = FileLoader(root=tmp_project, extensions={".py"})
        files = list(loader.load())
        names = {f.path.name for f in files}
        assert "README.md" not in names

    def test_loads_markdown_when_included(self, tmp_project: Path):
        loader = FileLoader(root=tmp_project, extensions={".py", ".md"})
        files = list(loader.load())
        names = {f.path.name for f in files}
        assert "README.md" in names

    def test_recurses_into_subdirectories(self, tmp_project: Path):
        loader = FileLoader(root=tmp_project, extensions={".py"})
        files = list(loader.load())
        names = {f.path.name for f in files}
        assert "helper.py" in names

    def test_source_file_has_correct_language(self, tmp_project: Path):
        loader = FileLoader(root=tmp_project, extensions={".py"})
        files = list(loader.load())
        for f in files:
            assert f.language == "python"

    def test_source_file_content_is_non_empty(self, tmp_project: Path):
        loader = FileLoader(root=tmp_project, extensions={".py"})
        files = list(loader.load())
        for f in files:
            assert f.content.strip()

    def test_invalid_root_raises(self, tmp_path: Path):
        loader = FileLoader(root=tmp_path / "nonexistent")
        with pytest.raises(ValueError, match="not a directory"):
            list(loader.load())

    def test_load_single_returns_source_file(self, tmp_project: Path):
        path = tmp_project / "main.py"
        loader = FileLoader(root=tmp_project)
        sf = loader.load_single(path)
        assert sf is not None
        assert "def add" in sf.content

    def test_load_single_returns_none_for_missing_file(self, tmp_project: Path):
        loader = FileLoader(root=tmp_project)
        sf = loader.load_single(tmp_project / "does_not_exist.py")
        assert sf is None

    def test_ignores_configured_dirs(self, tmp_path: Path):
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "cached.py").write_text("x = 1")
        loader = FileLoader(root=tmp_path, extensions={".py"})
        files = list(loader.load())
        names = {f.path.name for f in files}
        assert "cached.py" not in names

    def test_metadata_contains_relative_path(self, tmp_project: Path):
        loader = FileLoader(root=tmp_project, extensions={".py"})
        files = list(loader.load())
        for f in files:
            assert "relative_path" in f.metadata

    def test_size_bytes_positive(self, tmp_project: Path):
        loader = FileLoader(root=tmp_project, extensions={".py"})
        files = list(loader.load())
        for f in files:
            assert f.size_bytes > 0
