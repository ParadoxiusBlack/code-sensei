"""
tests/conftest.py
-----------------
Shared fixtures for all CodeSensei tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure the src/ layout is importable without installing the package.
# ---------------------------------------------------------------------------
SRC = Path(__file__).resolve().parents[1] / "src"
CONFIG = Path(__file__).resolve().parents[1] / "config"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(CONFIG) not in sys.path:
    sys.path.insert(0, str(CONFIG.parent))  # expose the config/ package


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal fake codebase in a temp directory."""
    (tmp_path / "main.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    (tmp_path / "utils.py").write_text(
        "def greet(name: str) -> str:\n    return f'Hello, {name}'\n"
    )
    (tmp_path / "README.md").write_text("# My Project\nA sample project.\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "helper.py").write_text("CONSTANT = 42\n")
    return tmp_path


@pytest.fixture()
def sample_source_file(tmp_path: Path):
    """Return a single SourceFile pointing at a real temp file."""
    from code_sensei.indexer.file_loader import SourceFile

    path = tmp_path / "sample.py"
    content = "def hello():\n    print('Hello, world!')\n"
    path.write_text(content)
    return SourceFile(path=path, content=content, language="python")
