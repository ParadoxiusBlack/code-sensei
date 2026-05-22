from __future__ import annotations

from pathlib import Path

import pytest


pytest.importorskip("PyQt6")


def test_run_gui_startup_smoke(monkeypatch, tmp_path: Path):
    """E2E smoke: GUI can initialize and exit cleanly in offscreen mode."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from code_sensei.gui import app as gui_app

    class _DummyVectorStore:
        @staticmethod
        def count() -> int:
            return 0

    class _DummyRetriever:
        vector_store = _DummyVectorStore()

    monkeypatch.setattr(gui_app, "_build_retriever", lambda _project_dir: _DummyRetriever())

    from PyQt6.QtWidgets import QApplication, QMainWindow

    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    monkeypatch.setattr(QMainWindow, "show", lambda self: None)

    exit_code = gui_app.run_gui(project_dir=str(tmp_path), top_k=4, use_llm=False)
    assert exit_code == 0
