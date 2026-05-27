from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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


def test_run_gui_full_workflow(monkeypatch, tmp_path: Path):
    """E2E smoke: ask, source select, chunk compare, and export all work together."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtCore import QThread
    from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QMainWindow, QMessageBox

    from code_sensei.assistant.qa import QAResponse
    from code_sensei.gui import app as gui_app
    from code_sensei.retrieval.retriever import RetrievalResult

    source_file = tmp_path / "src" / "sample.py"
    source_file.parent.mkdir(parents=True)
    source_text = (
        "def first():\n" "    return 'first'\n\n" "def second():\n" "    return 'second'\n"
    )
    source_file.write_text(source_text, encoding="utf-8")

    retrieval_results = [
        RetrievalResult(
            chunk_id="chunk-1",
            content=source_text[0:27],
            source_path="src/sample.py",
            language="python",
            score=0.92,
            metadata={"start_char": 0, "end_char": 27},
        ),
        RetrievalResult(
            chunk_id="chunk-2",
            content=source_text[28:],
            source_path="src/sample.py",
            language="python",
            score=0.83,
            metadata={"start_char": 28, "end_char": len(source_text)},
        ),
    ]

    class _DummyVectorStore:
        @staticmethod
        def count() -> int:
            return 2

    class _DummyRetriever:
        def __init__(self):
            self.vector_store = _DummyVectorStore()
            self.last_metrics = SimpleNamespace(embed_ms=1.0, vector_query_ms=2.0, avg_score=0.875)

    class _DummyQA:
        def __init__(self, retriever, top_k=8, **kwargs):
            self.retriever = retriever
            self.top_k = top_k
            self.last_query_metrics = None
            self.llm_init_error = None

        def ask(self, question, language_filter=None, path_prefix=None, use_llm=True):
            self.last_query_metrics = SimpleNamespace(
                total_ms=12.0,
                retrieval_ms=4.0,
                generation_ms=8.0,
                result_count=2,
                source_count=1,
            )
            return QAResponse(
                question=question,
                answer="Found matching code.",
                sources=["src/sample.py"],
                retrieval_results=retrieval_results,
            )

    export_path = tmp_path / "sample.annotated.py"
    diff_dialog_titles: list[str] = []

    monkeypatch.setattr(gui_app, "_build_retriever", lambda _project_dir: _DummyRetriever())
    monkeypatch.setattr(gui_app, "CodeQA", _DummyQA)
    monkeypatch.setattr(QMainWindow, "show", lambda self: None)
    monkeypatch.setattr(QThread, "start", lambda self: self.started.emit())
    monkeypatch.setattr(QThread, "quit", lambda self: self.finished.emit())
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(export_path), "")
    )
    monkeypatch.setattr(
        QDialog, "exec", lambda self: diff_dialog_titles.append(self.windowTitle()) or 0
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: 0)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: 0)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: 0)

    def _run_exec(self):
        window = next(
            widget for widget in QApplication.topLevelWidgets() if hasattr(widget, "question_input")
        )
        window.question_input.setText("Where is the sample code?")
        response = window.qa.ask("Where is the sample code?", use_llm=False)
        window._on_query_finished(
            SimpleNamespace(
                answer=response.answer,
                sources=response.sources,
                retrieval_results=response.retrieval_results,
            )
        )

        assert window.sources_list.count() == 1
        window.sources_list.setCurrentRow(0)
        assert "CHUNK" in window.code_view.toPlainText()
        assert window.export_button.isEnabled()

        window._on_chunk_clicked(0)
        window._on_chunk_ctrl_clicked(0)
        window._on_chunk_ctrl_clicked(1)
        assert window.compare_button.isEnabled()

        window._on_compare_chunks()
        window._on_export()

        exported = export_path.read_text(encoding="utf-8")
        assert "File: src/sample.py" in exported
        assert "CHUNK" in exported
        assert diff_dialog_titles
        return 0

    monkeypatch.setattr(QApplication, "exec", _run_exec)

    exit_code = gui_app.run_gui(project_dir=str(tmp_path), top_k=4, use_llm=False)
    assert exit_code == 0
