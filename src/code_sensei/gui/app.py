"""
gui/app.py
----------
PyQt6 desktop front-end for CodeSensei.

Features
~~~~~~~~
- Ask questions against indexed project context.
- Show answer and source files.
- Preview source chunks in a code viewer panel.
- Select any project folder and auto-index it.
- Explore and edit project files from an in-app file tree.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from code_sensei.assistant.qa import CodeQA
from code_sensei.indexer.chunker import Chunker
from code_sensei.indexer.embedder import Embedder
from code_sensei.indexer.file_loader import FileLoader
from code_sensei.retrieval.retriever import RetrievalResult, Retriever
from code_sensei.retrieval.vector_store import VectorStore

try:
    from config.settings import EMBEDDING_MODEL, EMBEDDING_PROVIDER
except ImportError:
    EMBEDDING_MODEL = "nomic-embed-text"
    EMBEDDING_PROVIDER = "ollama"


def _sanitize_collection_part(value: str) -> str:
    """Convert provider/model names into a stable Chroma-safe token."""
    import re

    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_").lower() or "default"


def _collection_name_for_project(project_dir: Path) -> str:
    project_name = project_dir.name or "code_sensei_default"
    provider = _sanitize_collection_part(EMBEDDING_PROVIDER)
    model = _sanitize_collection_part(EMBEDDING_MODEL)
    return f"{project_name}__{provider}__{model}"


def _is_editable_text_file(path: Path, max_size_bytes: int = 2_000_000) -> bool:
    """Return True when a file looks safe for text editing in the GUI."""
    if not path.exists() or not path.is_file():
        return False
    if path.stat().st_size > max_size_bytes:
        return False
    # Conservative list for source/doc/config text files.
    editable_exts = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".kt", ".go", ".rb", ".rs",
        ".c", ".cpp", ".h", ".hpp", ".cs", ".php", ".swift", ".scala", ".sh", ".bash",
        ".yaml", ".yml", ".toml", ".json", ".md", ".rst", ".txt", ".ini", ".cfg",
        ".html", ".css", ".sql", ".xml",
    }
    return path.suffix.lower() in editable_exts


def _read_source_excerpt(path: str, max_chars: int = 6000, base_dir: Path | None = None) -> str:
    """Read and truncate a source file safely for viewer display."""
    p = Path(path)
    if base_dir is not None and not p.is_absolute():
        p = (base_dir / p).resolve()
    if not p.exists() or not p.is_file():
        return "[Source file is missing or unavailable.]"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"[Failed to read source: {exc}]"
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n# ...truncated"


@dataclass
class QueryResult:
    answer: str
    sources: list[str]
    retrieval_results: list[RetrievalResult]


@dataclass
class IndexResult:
    root: Path
    total_files: int
    total_chunks: int


def _build_retriever(project_dir: Path) -> Retriever:
    collection = _collection_name_for_project(project_dir)
    vector_store = VectorStore(collection_name=collection)
    vector_store.connect()
    embedder = Embedder()
    return Retriever(vector_store=vector_store, embedder=embedder)


def _index_project(
    project_dir: Path,
    progress_cb: Callable[[str], None] | None = None,
) -> tuple[int, int]:
    """Index a project and return (total_files, total_chunks)."""
    loader = FileLoader(root=project_dir)
    chunker = Chunker()
    embedder = Embedder()

    collection = _collection_name_for_project(project_dir)
    vector_store = VectorStore(collection_name=collection)
    vector_store.connect()

    total_files = 0
    total_chunks = 0

    for source_file in loader.load():
        total_files += 1
        if progress_cb is not None and (total_files == 1 or total_files % 20 == 0):
            progress_cb(f"Indexing... {total_files} files")

        chunks = chunker.chunk_file(source_file)
        embedded = embedder.embed_chunks(chunks)
        vector_store.upsert(embedded)
        total_chunks += len(chunks)

    return total_files, total_chunks


def run_gui(project_dir: str = ".", top_k: int = 8, use_llm: bool = True) -> int:
    """Launch the desktop GUI application.

    Returns process exit code.
    """
    try:
        from PyQt6.QtCore import QObject, QThread, pyqtSignal
        from PyQt6.QtGui import QFont, QFileSystemModel
        from PyQt6.QtWidgets import (
            QApplication,
            QCheckBox,
            QFileDialog,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QPlainTextEdit,
            QSplitter,
            QTabWidget,
            QTextEdit,
            QTreeView,
            QVBoxLayout,
            QWidget,
        )
    except Exception as exc:
        raise RuntimeError(
            "PyQt6 GUI imports failed. Install with: pip install PyQt6. "
            f"Original error: {exc}"
        ) from exc

    class QueryWorker(QObject):
        finished = pyqtSignal(object)
        failed = pyqtSignal(str)

        def __init__(self, qa: CodeQA, question: str, use_llm_local: bool):
            super().__init__()
            self.qa = qa
            self.question = question
            self.use_llm_local = use_llm_local

        def run(self) -> None:
            try:
                response = self.qa.ask(question=self.question, use_llm=self.use_llm_local)
                self.finished.emit(
                    QueryResult(
                        answer=response.answer,
                        sources=response.sources,
                        retrieval_results=response.retrieval_results,
                    )
                )
            except Exception as exc:
                self.failed.emit(str(exc))

    class IndexWorker(QObject):
        progress = pyqtSignal(str)
        finished = pyqtSignal(object)
        failed = pyqtSignal(str)

        def __init__(self, root: Path):
            super().__init__()
            self.root = root

        def run(self) -> None:
            try:
                total_files, total_chunks = _index_project(self.root, progress_cb=self.progress.emit)
                self.finished.emit(
                    IndexResult(root=self.root, total_files=total_files, total_chunks=total_chunks)
                )
            except Exception as exc:
                self.failed.emit(str(exc))

    class MainWindow(QMainWindow):
        def __init__(self, root: Path, qa: CodeQA):
            super().__init__()
            self.root = root
            self.qa = qa
            self.top_k = top_k
            self._latest_results: list[RetrievalResult] = []

            self._query_thread: QThread | None = None
            self._query_worker: QueryWorker | None = None
            self._index_thread: QThread | None = None
            self._index_worker: IndexWorker | None = None

            self._current_edit_file: Path | None = None
            self._build_ui()
            self._set_project_root(self.root)
            self._refresh_project_status()

        def _build_ui(self) -> None:
            self.resize(1400, 860)

            root_widget = QWidget()
            root_layout = QVBoxLayout(root_widget)

            # Top project bar
            project_row = QHBoxLayout()
            self.project_label = QLabel("")
            project_row.addWidget(self.project_label, stretch=1)

            self.select_project_button = QPushButton("Select Project...")
            self.select_project_button.clicked.connect(self._on_select_project)
            project_row.addWidget(self.select_project_button)

            self.reindex_button = QPushButton("Reindex")
            self.reindex_button.clicked.connect(self._on_reindex_current_project)
            project_row.addWidget(self.reindex_button)

            root_layout.addLayout(project_row)

            splitter = QSplitter()

            # Left pane: chat/answer interaction
            left = QWidget()
            left_layout = QVBoxLayout(left)

            self.answer_view = QTextEdit()
            self.answer_view.setReadOnly(True)
            self.answer_view.setPlaceholderText("Ask a question to get an answer here...")
            left_layout.addWidget(QLabel("Answer"))
            left_layout.addWidget(self.answer_view)

            input_row = QHBoxLayout()
            self.question_input = QLineEdit()
            self.question_input.setPlaceholderText("How does indexing work?")
            self.question_input.returnPressed.connect(self._on_ask)
            input_row.addWidget(self.question_input)

            self.llm_checkbox = QCheckBox("Use LLM")
            self.llm_checkbox.setChecked(use_llm)
            input_row.addWidget(self.llm_checkbox)

            self.ask_button = QPushButton("Ask")
            self.ask_button.clicked.connect(self._on_ask)
            input_row.addWidget(self.ask_button)
            left_layout.addLayout(input_row)

            # Right pane: tabs for retrieval view and project files
            right_tabs = QTabWidget()

            # Retrieval tab
            retrieval_tab = QWidget()
            retrieval_layout = QVBoxLayout(retrieval_tab)
            retrieval_layout.addWidget(QLabel("Sources"))
            self.sources_list = QListWidget()
            self.sources_list.currentRowChanged.connect(self._on_source_selected)
            retrieval_layout.addWidget(self.sources_list)

            retrieval_layout.addWidget(QLabel("Code Viewer"))
            self.code_view = QPlainTextEdit()
            self.code_view.setReadOnly(True)
            self.code_view.setFont(QFont("Consolas", 10))
            self.code_view.setPlaceholderText("Select a source to preview code...")
            retrieval_layout.addWidget(self.code_view)
            right_tabs.addTab(retrieval_tab, "Retrieved Source")

            # Project files tab
            files_tab = QWidget()
            files_layout = QVBoxLayout(files_tab)

            files_split = QSplitter()

            self.file_model = QFileSystemModel()
            self.file_model.setReadOnly(True)
            self.file_tree = QTreeView()
            self.file_tree.setModel(self.file_model)
            self.file_tree.clicked.connect(self._on_file_tree_clicked)
            files_split.addWidget(self.file_tree)

            editor_container = QWidget()
            editor_layout = QVBoxLayout(editor_container)
            self.editor_path_label = QLabel("No file selected")
            editor_layout.addWidget(self.editor_path_label)

            self.file_editor = QPlainTextEdit()
            self.file_editor.setFont(QFont("Consolas", 10))
            self.file_editor.setPlaceholderText("Open a file from the tree to edit...")
            editor_layout.addWidget(self.file_editor)

            editor_actions = QHBoxLayout()
            self.save_file_button = QPushButton("Save File")
            self.save_file_button.clicked.connect(self._save_current_file)
            editor_actions.addWidget(self.save_file_button)
            editor_layout.addLayout(editor_actions)

            files_split.addWidget(editor_container)
            files_split.setStretchFactor(0, 2)
            files_split.setStretchFactor(1, 3)

            files_layout.addWidget(files_split)
            right_tabs.addTab(files_tab, "Project Files")

            splitter.addWidget(left)
            splitter.addWidget(right_tabs)
            splitter.setStretchFactor(0, 2)
            splitter.setStretchFactor(1, 3)

            root_layout.addWidget(splitter)

            self.status_label = QLabel("Ready")
            root_layout.addWidget(self.status_label)

            self.setCentralWidget(root_widget)

        def _set_project_root(self, root: Path) -> None:
            self.root = root.resolve()
            self.setWindowTitle(f"CodeSensei GUI — {self.root}")

            model_index = self.file_model.setRootPath(str(self.root))
            self.file_tree.setRootIndex(model_index)

        def _set_busy(self, busy: bool) -> None:
            self.ask_button.setEnabled(not busy)
            self.question_input.setEnabled(not busy)
            self.select_project_button.setEnabled(not busy)
            self.reindex_button.setEnabled(not busy)
            self.save_file_button.setEnabled(not busy)
            self.ask_button.setText("Thinking..." if busy else "Ask")

        def _refresh_project_status(self) -> None:
            indexed_chunks = 0
            try:
                indexed_chunks = self.qa.retriever.vector_store.count()
            except Exception:
                indexed_chunks = 0

            self.project_label.setText(
                f"Project: {self.root}  |  Indexed chunks: {indexed_chunks}"
            )
            self.setWindowTitle(f"CodeSensei GUI — {self.root}")

        def _append_status(self, text: str) -> None:
            self.status_label.setText(text)

        def _on_ask(self) -> None:
            question = self.question_input.text().strip()
            if not question:
                return
            if self._index_thread is not None:
                QMessageBox.information(
                    self,
                    "Indexing in Progress",
                    "Please wait for indexing to finish before asking questions.",
                )
                return

            self._set_busy(True)
            self.answer_view.append(f"\n> {question}\n")

            self._query_thread = QThread()
            self._query_worker = QueryWorker(self.qa, question, self.llm_checkbox.isChecked())
            self._query_worker.moveToThread(self._query_thread)

            self._query_thread.started.connect(self._query_worker.run)
            self._query_worker.finished.connect(self._on_query_finished)
            self._query_worker.failed.connect(self._on_query_failed)

            # Ensure thread cleanup
            self._query_worker.finished.connect(self._query_thread.quit)
            self._query_worker.failed.connect(self._query_thread.quit)
            self._query_thread.finished.connect(self._query_thread.deleteLater)
            self._query_thread.finished.connect(self._on_query_thread_finished)
            self._query_thread.start()

        def _on_query_finished(self, result: QueryResult) -> None:
            self._latest_results = result.retrieval_results

            self.answer_view.append(result.answer.strip() or "[No answer text returned]")

            self.sources_list.clear()
            for src in result.sources:
                QListWidgetItem(src, self.sources_list)

            if result.sources:
                self.sources_list.setCurrentRow(0)

        def _on_query_failed(self, error_message: str) -> None:
            QMessageBox.critical(self, "Query Error", error_message)

        def _on_query_thread_finished(self) -> None:
            self._query_thread = None
            self._query_worker = None
            self._set_busy(False)
            self._append_status("Ready")

        def _on_source_selected(self, row: int) -> None:
            if row < 0:
                self.code_view.clear()
                return

            src_path = self.sources_list.item(row).text()
            selected: RetrievalResult | None = None
            for r in self._latest_results:
                if r.source_path == src_path:
                    selected = r
                    break

            if selected:
                snippet = selected.content
                header = (
                    f"# File: {selected.source_path}\n"
                    f"# Language: {selected.language}\n"
                    f"# Score: {selected.score:.2f}\n\n"
                )
                self.code_view.setPlainText(header + snippet)
                return

            # Fallback to reading file if no retrieval snippet is available.
            self.code_view.setPlainText(_read_source_excerpt(src_path, base_dir=self.root))

        def _on_select_project(self) -> None:
            selected = QFileDialog.getExistingDirectory(
                self,
                "Select Project Folder",
                str(self.root),
            )
            if not selected:
                return

            new_root = Path(selected).resolve()
            self._start_index_for_project(new_root)

        def _on_reindex_current_project(self) -> None:
            self._start_index_for_project(self.root)

        def _start_index_for_project(self, root: Path) -> None:
            if self._index_thread is not None:
                return

            self._set_busy(True)
            self._set_project_root(root)
            self._append_status("Starting index...")
            self.answer_view.append(f"\n[Index] Auto-indexing project: {root}\n")

            self._index_thread = QThread()
            self._index_worker = IndexWorker(root)
            self._index_worker.moveToThread(self._index_thread)

            self._index_thread.started.connect(self._index_worker.run)
            self._index_worker.progress.connect(self._on_index_progress)
            self._index_worker.finished.connect(self._on_index_finished)
            self._index_worker.failed.connect(self._on_index_failed)

            self._index_worker.finished.connect(self._index_thread.quit)
            self._index_worker.failed.connect(self._index_thread.quit)
            self._index_thread.finished.connect(self._index_thread.deleteLater)
            self._index_thread.finished.connect(self._on_index_thread_finished)
            self._index_thread.start()

        def _on_index_progress(self, text: str) -> None:
            self._append_status(text)

        def _on_index_finished(self, result: IndexResult) -> None:
            self._set_project_root(result.root)
            retriever = _build_retriever(result.root)
            self.qa = CodeQA(retriever=retriever, top_k=self.top_k)
            self._latest_results = []
            self.sources_list.clear()
            self.code_view.clear()
            self._refresh_project_status()

            self.answer_view.append(
                "[Index complete] "
                f"Files: {result.total_files}, chunks: {result.total_chunks}\n"
            )

        def _on_index_failed(self, error_message: str) -> None:
            QMessageBox.critical(self, "Indexing Error", error_message)
            self._append_status("Indexing failed")

        def _on_index_thread_finished(self) -> None:
            self._index_thread = None
            self._index_worker = None
            self._set_busy(False)
            self._append_status("Ready")

        def _on_file_tree_clicked(self, model_index) -> None:  # type: ignore[no-untyped-def]
            path_str = self.file_model.filePath(model_index)
            p = Path(path_str)
            if not p.is_file():
                return

            if not _is_editable_text_file(p):
                self.editor_path_label.setText(f"Not editable in GUI: {p}")
                self.file_editor.setPlainText("[Binary or unsupported file type.]")
                self._current_edit_file = None
                return

            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                QMessageBox.critical(self, "Open File Error", str(exc))
                return

            self._current_edit_file = p
            self.editor_path_label.setText(str(p))
            self.file_editor.setPlainText(text)

        def _save_current_file(self) -> None:
            if self._current_edit_file is None:
                QMessageBox.information(self, "No File Selected", "Select a file first.")
                return

            try:
                self._current_edit_file.write_text(
                    self.file_editor.toPlainText(), encoding="utf-8", errors="replace"
                )
            except Exception as exc:
                QMessageBox.critical(self, "Save Error", str(exc))
                return

            self._append_status(f"Saved: {self._current_edit_file}")
            self.answer_view.append(f"[Saved] {self._current_edit_file}\n")

    app = QApplication(sys.argv)

    root = Path(project_dir).resolve()
    retriever = _build_retriever(root)
    qa = CodeQA(retriever=retriever, top_k=top_k)

    window = MainWindow(root=root, qa=qa)
    window.show()
    return app.exec()


def main_gui() -> int:
    """Entry point for the GUI application when installed as a package.
    
    Launches the GUI from the current working directory or opens a folder picker.
    """
    import os
    
    # Try to use current directory if it's a code project, otherwise start with home
    project_dir = os.getcwd()
    return run_gui(project_dir=project_dir, top_k=8, use_llm=True)
