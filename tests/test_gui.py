from __future__ import annotations

from pathlib import Path

from code_sensei.gui.app import (
    _collection_name_for_project,
    _is_editable_text_file,
    _read_source_excerpt,
    _sanitize_collection_part,
)


def test_sanitize_collection_part():
    assert _sanitize_collection_part("nomic/embed:text") == "nomic_embed_text"


def test_collection_name_for_project(tmp_path: Path):
    project_dir = tmp_path / "demo-project"
    project_dir.mkdir(parents=True)

    name = _collection_name_for_project(project_dir)

    assert name.startswith("demo-project__")
    assert "__" in name


def test_read_source_excerpt_missing_file(tmp_path: Path):
    missing = tmp_path / "missing.py"

    excerpt = _read_source_excerpt(str(missing))

    assert "missing" in excerpt.lower() or "unavailable" in excerpt.lower()


def test_read_source_excerpt_truncates(tmp_path: Path):
    p = tmp_path / "big.py"
    p.write_text("x" * 120)

    excerpt = _read_source_excerpt(str(p), max_chars=40)

    assert "truncated" in excerpt.lower()
    assert len(excerpt) > 40


def test_read_source_excerpt_uses_base_dir_for_relative_path(tmp_path: Path):
    project = tmp_path / "some-project"
    project.mkdir(parents=True)
    p = project / "src" / "module.py"
    p.parent.mkdir(parents=True)
    p.write_text("print('ok')")

    excerpt = _read_source_excerpt("src/module.py", base_dir=project)

    assert "print('ok')" in excerpt


def test_is_editable_text_file_accepts_source_file(tmp_path: Path):
    p = tmp_path / "main.py"
    p.write_text("print('ok')")

    assert _is_editable_text_file(p) is True


def test_is_editable_text_file_rejects_large_file(tmp_path: Path):
    p = tmp_path / "big.py"
    p.write_text("x" * 3000)

    assert _is_editable_text_file(p, max_size_bytes=1000) is False


def test_is_editable_text_file_rejects_unsupported_extension(tmp_path: Path):
    p = tmp_path / "data.bin"
    p.write_text("text")

    assert _is_editable_text_file(p) is False
