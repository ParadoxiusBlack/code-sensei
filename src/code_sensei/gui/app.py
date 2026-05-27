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

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

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
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".kt",
        ".go",
        ".rb",
        ".rs",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".php",
        ".swift",
        ".scala",
        ".sh",
        ".bash",
        ".yaml",
        ".yml",
        ".toml",
        ".json",
        ".md",
        ".rst",
        ".txt",
        ".ini",
        ".cfg",
        ".html",
        ".css",
        ".sql",
        ".xml",
    }
    return path.suffix.lower() in editable_exts


def _read_full_file(path: str, base_dir: Path | None = None) -> str:
    """Read a complete source file (no truncation)."""
    p = Path(path)
    if base_dir is not None and not p.is_absolute():
        p = (base_dir / p).resolve()
    if not p.exists() or not p.is_file():
        return "[Source file is missing or unavailable.]"
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"[Failed to read source: {exc}]"


def _annotate_file_with_chunks(
    file_content: str,
    chunk_ranges: list[tuple[int, int]],
    current_chunk_range: tuple[int, int] | None = None,
    chunk_scores: dict[int, float] | None = None,
) -> str:
    """
    Annotate file content with chunk boundary markers and scores.

    Shows visual indicators for chunk boundaries and optionally displays relevance scores.

    Args:
        file_content: Full file text
        chunk_ranges: List of (start_char, end_char) tuples for each chunk
        current_chunk_range: Optional (start_char, end_char) of currently selected chunk
        chunk_scores: Optional dict mapping chunk_index to relevance score (0-1)
    """
    if not chunk_ranges:
        return file_content

    # Sort ranges for processing
    sorted_ranges = sorted(set(chunk_ranges))

    # Build annotated version with line numbers and chunk indicators
    lines = file_content.split("\n")
    char_pos = 0
    annotated_lines = []
    for line_num, line in enumerate(lines, 1):
        line_end = char_pos + len(line) + 1  # +1 for newline

        # Check which chunks contain this line
        chunks_at_line = []
        for i, (start, end) in enumerate(sorted_ranges):
            if (
                start <= char_pos < end
                or start < line_end <= end
                or (start < char_pos and line_end <= end)
            ):
                chunks_at_line.append(i)

        # Add line number and chunk indicators
        indicator = ""
        if chunks_at_line:
            is_current = current_chunk_range and (
                current_chunk_range[0] <= char_pos < current_chunk_range[1]
                or current_chunk_range[0] < line_end <= current_chunk_range[1]
            )
            marker = "▶" if is_current else "│"

            # Build chunk marker with optional scores
            chunk_markers = []
            for chunk_idx in chunks_at_line:
                if chunk_scores and chunk_idx in chunk_scores:
                    score = chunk_scores[chunk_idx]
                    chunk_markers.append(f"{chunk_idx+1}|{score:.2f}")
                else:
                    chunk_markers.append(str(chunk_idx + 1))

            chunk_nums = f"[{','.join(chunk_markers)}]"
            indicator = f" {marker} CHUNK{chunk_nums}"

        annotated_lines.append(f"{line_num:4d} | {line}{indicator}")
        char_pos = line_end

    # Add header with legend
    legend_score_line = (
        "│ [1|0.87] = Chunk 1 with relevance score 0.87                │\n"
        if chunk_scores
        else "│ [1] = Chunk index                                               │\n"
    )

    header = (
        "┌─ FULL FILE VIEW WITH CHUNK INDICATORS ─────────────────────┐\n"
        "│ │   = Line is part of a chunk retrieved by LLM             │\n"
        "│ ▶   = Line is in the CURRENT chunk being viewed            │\n"
        + legend_score_line
        + "└────────────────────────────────────────────────────────────┘\n\n"
    )

    return header + "\n".join(annotated_lines)


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
        from PyQt6.QtCore import QObject, QSize, Qt, QThread, pyqtSignal
        from PyQt6.QtGui import QColor, QFileSystemModel, QFont, QPainter, QTextCursor
        from PyQt6.QtWidgets import (
            QApplication,
            QCheckBox,
            QDialog,
            QFileDialog,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QPushButton,
            QSplitter,
            QTabWidget,
            QTextEdit,
            QTreeView,
            QVBoxLayout,
            QWidget,
        )
    except Exception as exc:
        raise RuntimeError(
            "PyQt6 GUI imports failed. Install with: pip install PyQt6. " f"Original error: {exc}"
        ) from exc

    class ClickableCodeView(QPlainTextEdit):
        """QPlainTextEdit with clickable chunk markers."""

        chunk_clicked = pyqtSignal(int)  # Emits chunk index when clicked
        chunk_ctrl_clicked = pyqtSignal(int)  # Emits chunk index when Ctrl+clicked

        def __init__(self, parent=None):
            super().__init__(parent)
            self.chunk_ranges = {}  # {chunk_index: (start_char, end_char)}
            self.current_selection = None

        def set_chunk_ranges(self, chunk_ranges):
            """Store chunk index to range mapping."""
            self.chunk_ranges = chunk_ranges

        def mousePressEvent(self, event):
            """Detect clicks on chunk markers like [1], [2], etc."""
            cursor = self.cursorForPosition(event.pos())
            block = cursor.block()
            text = block.text()

            # Find chunk marker at cursor position
            col = cursor.positionInBlock()
            chunk_idx = self._extract_chunk_at_position(text, col)

            if chunk_idx is not None:
                # Check if Ctrl is pressed for multi-select comparison
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    self.chunk_ctrl_clicked.emit(chunk_idx)
                else:
                    self.chunk_clicked.emit(chunk_idx)
                event.accept()
                return

            super().mousePressEvent(event)

        def _extract_chunk_at_position(self, line_text: str, col: int) -> int | None:
            """Extract chunk index from text at column, e.g., [1], [1|0.87], or [1,2|0.85]."""
            # Find all chunk markers in the line (supports optional scores)
            for match in re.finditer(r"\[(\d+(?:\|[\d.]+)?(?:,\d+(?:\|[\d.]+)?)*)\]", line_text):
                if match.start() <= col <= match.end():
                    # Clicked on a chunk marker, extract first index (strip score if present)
                    content = match.group(1)
                    first_chunk = content.split(",")[0]  # Get first chunk marker
                    chunk_num = first_chunk.split("|")[0]  # Extract number before score
                    return int(chunk_num) - 1  # Convert to 0-based

            return None

        def scroll_to_chunk(self, start_char: int, end_char: int) -> None:
            """Scroll to display the chunk."""
            cursor = self.textCursor()
            cursor.setPosition(start_char)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()

        def highlight_chunk(self, start_char: int, end_char: int) -> None:
            """Highlight all lines in the chunk."""
            cursor = self.textCursor()
            cursor.setPosition(start_char)
            cursor.setPosition(end_char, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)

    class ChunkMinimap(QWidget):
        """Visual minimap of chunk positions and density in the file."""

        chunk_clicked = pyqtSignal(int)  # Emits chunk index when minimap chunk is clicked

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFixedWidth(40)
            self.chunk_ranges = {}  # {chunk_index: (start_char, end_char)}
            self.chunk_scores = {}  # {chunk_index: score}
            self.file_size = 1  # Total file characters
            self.current_chunk_range = None
            self.selected_chunks_for_diff = []

        def set_data(self, chunk_ranges: dict, chunk_scores: dict, file_size: int):
            """Update minimap with chunk data."""
            self.chunk_ranges = chunk_ranges
            self.chunk_scores = chunk_scores
            self.file_size = max(1, file_size)  # Avoid division by zero
            self.update()  # Trigger repaint

        def set_current_chunk(self, chunk_range: tuple[int, int] | None):
            """Highlight the currently selected chunk."""
            self.current_chunk_range = chunk_range
            self.update()

        def set_selected_for_diff(self, selected: list[int]):
            """Set chunks selected for diff comparison."""
            self.selected_chunks_for_diff = selected
            self.update()

        def sizeHint(self) -> QSize:
            """Preferred size."""
            return QSize(40, 400)

        def paintEvent(self, event):
            """Draw the minimap."""
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(240, 240, 240))  # Light gray background
            painter.drawRect(0, 0, self.width() - 1, self.height() - 1)  # Border

            if not self.chunk_ranges or self.file_size <= 0:
                painter.end()
                return

            # Draw each chunk as a colored rectangle
            usable_height = self.height() - 4

            for chunk_idx, (start_char, end_char) in self.chunk_ranges.items():
                # Calculate position and height proportional to file size
                chunk_start_ratio = start_char / self.file_size
                chunk_end_ratio = end_char / self.file_size

                y_start = int(2 + chunk_start_ratio * usable_height)
                y_end = int(2 + chunk_end_ratio * usable_height)
                height = max(1, y_end - y_start)

                # Choose color based on state
                if chunk_idx in self.selected_chunks_for_diff:
                    # Orange for diff-selected chunks
                    color = QColor(255, 140, 0)
                elif self.current_chunk_range and (
                    self.current_chunk_range[0] <= start_char < self.current_chunk_range[1]
                ):
                    # Green for current chunk
                    color = QColor(0, 200, 0)
                else:
                    # Blue for regular chunks, darker if higher score
                    score = self.chunk_scores.get(chunk_idx, 0.5)
                    intensity = int(100 + score * 155)  # 100-255 based on score
                    color = QColor(50, 100, intensity)

                # Draw chunk rectangle
                painter.fillRect(2, y_start, self.width() - 4, height, color)

            painter.end()

        def mousePressEvent(self, event):
            """Allow clicking on minimap to jump to chunk."""
            if not self.chunk_ranges or self.file_size <= 0:
                return

            # Calculate which chunk was clicked
            usable_height = self.height() - 4
            click_ratio = (event.pos().y() - 2) / usable_height if usable_height > 0 else 0
            click_char = int(click_ratio * self.file_size)

            # Find chunk at clicked position
            for chunk_idx, (start_char, end_char) in self.chunk_ranges.items():
                if start_char <= click_char < end_char:
                    self.chunk_clicked.emit(chunk_idx)
                    break

    class DiffDialog(QDialog):
        """Dialog for displaying diff between two chunks."""

        def __init__(self, parent, title: str, diff_text: str, content1: str, content2: str):
            super().__init__(parent)
            self.setWindowTitle(title)
            self.resize(1000, 600)

            layout = QVBoxLayout()

            # Info label
            info_label = QLabel("Showing unified diff of code changes")
            layout.addWidget(info_label)

            # Diff viewer
            diff_view = QPlainTextEdit()
            diff_view.setReadOnly(True)
            diff_view.setFont(QFont("Courier", 9))

            # Color the diff output for better readability
            if diff_text:
                diff_view.setPlainText(diff_text)
            else:
                diff_view.setPlainText("No differences found between chunks.")

            layout.addWidget(diff_view)

            # Close button
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.accept)
            layout.addWidget(close_btn)

            self.setLayout(layout)

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
                total_files, total_chunks = _index_project(
                    self.root, progress_cb=self.progress.emit
                )
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

            # Chunk tracking for clickable markers
            self._chunk_index_map = {}  # {chunk_index: (start_char, end_char)}
            self._current_chunk_selection = None

            # Chunk diff comparison tracking
            self._selected_chunks_for_diff = []  # List of max 2 chunk indices for comparison
            self._chunk_content_map = {}  # {chunk_index: chunk_content}

            # Track current source for export
            self._current_source_path: str | None = None
            self._current_display_content: str = ""  # Full displayed text including header

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

            # Code viewer with minimap sidebar
            code_viewer_row = QHBoxLayout()
            self.code_view = ClickableCodeView()
            self.code_view.setReadOnly(True)
            self.code_view.setFont(QFont("Consolas", 10))
            self.code_view.setPlaceholderText("Select a source to preview code...")
            self.code_view.chunk_clicked.connect(self._on_chunk_clicked)
            self.code_view.chunk_ctrl_clicked.connect(self._on_chunk_ctrl_clicked)
            code_viewer_row.addWidget(self.code_view, stretch=1)

            self.minimap = ChunkMinimap()
            self.minimap.chunk_clicked.connect(self._on_chunk_clicked)
            code_viewer_row.addWidget(self.minimap)

            retrieval_layout.addLayout(code_viewer_row)

            # Compare chunks button and export button
            compare_row = QHBoxLayout()
            self.compare_button = QPushButton("Compare Selected Chunks (Ctrl+Click 2)")
            self.compare_button.clicked.connect(self._on_compare_chunks)
            self.compare_button.setEnabled(False)
            self.export_button = QPushButton("Export Annotated File")
            self.export_button.clicked.connect(self._on_export)
            self.export_button.setEnabled(False)
            compare_row.addStretch()
            compare_row.addWidget(self.compare_button)
            compare_row.addWidget(self.export_button)
            retrieval_layout.addLayout(compare_row)

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

            self.project_label.setText(f"Project: {self.root}  |  Indexed chunks: {indexed_chunks}")
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

            # Find ALL chunks from this file in the retrieval results
            chunks_from_file = [r for r in self._latest_results if r.source_path == src_path]

            if not chunks_from_file:
                # Fallback: show file if no chunks available
                content = _read_full_file(src_path, base_dir=self.root)
                self.code_view.setPlainText(content)
                self._chunk_index_map = {}
                self.code_view.set_chunk_ranges({})
                return

            # Extract char ranges and scores from chunks
            chunk_ranges = []
            chunk_scores = {}
            first_chunk = chunks_from_file[0]

            # Read full file once for extracting chunk contents
            file_content = _read_full_file(src_path, base_dir=self.root)

            # Build chunk content map for diff comparison
            self._chunk_content_map = {}
            for idx, chunk in enumerate(chunks_from_file):
                if "start_char" in chunk.metadata and "end_char" in chunk.metadata:
                    start_char = chunk.metadata["start_char"]
                    end_char = chunk.metadata["end_char"]
                    chunk_ranges.append((start_char, end_char))
                    chunk_scores[idx] = chunk.score

                    # Extract chunk content for diff comparison
                    self._chunk_content_map[idx] = file_content[start_char:end_char]

            # Build chunk index map for clickable markers
            self._chunk_index_map = {}
            for idx, chunk_range in enumerate(chunk_ranges):
                self._chunk_index_map[idx] = chunk_range
            self.code_view.set_chunk_ranges(self._chunk_index_map)

            # Use current chunk selection if available, otherwise use first chunk
            current_range = self._current_chunk_selection or (
                (first_chunk.metadata.get("start_char"), first_chunk.metadata.get("end_char"))
                if "start_char" in first_chunk.metadata and "end_char" in first_chunk.metadata
                else None
            )

            if chunk_ranges:
                annotated_content = _annotate_file_with_chunks(
                    file_content, chunk_ranges, current_range, chunk_scores
                )
            else:
                annotated_content = file_content

            # Build comprehensive header
            num_chunks = len(chunks_from_file)
            avg_score = sum(c.score for c in chunks_from_file) / len(chunks_from_file)

            header = (
                f"╔════════════════════════════════════════════════════════════╗\n"
                f"║  File: {src_path}\n"
                f"║  Language: {first_chunk.language}\n"
                f"║  Retrieved Chunks: {num_chunks} | Avg Score: {avg_score:.2f}\n"
                f"║  ✓ Showing FULL file with chunk indicators (not truncated)\n"
                f"╚════════════════════════════════════════════════════════════╝\n\n"
            )

            full_display = header + annotated_content
            self.code_view.setPlainText(full_display)

            # Store current source for export
            self._current_source_path = src_path
            self._current_display_content = full_display
            self.export_button.setEnabled(True)

            # Update minimap with chunk data
            self.minimap.set_data(self._chunk_index_map, chunk_scores, len(file_content))
            if current_range:
                self.minimap.set_current_chunk(current_range)
            self.minimap.set_selected_for_diff(self._selected_chunks_for_diff)

        def _on_chunk_clicked(self, chunk_index: int) -> None:
            """Handle click on a chunk marker [1], [2], etc."""
            if chunk_index not in self._chunk_index_map:
                return

            start_char, end_char = self._chunk_index_map[chunk_index]
            self._current_chunk_selection = (start_char, end_char)

            # Scroll to and highlight the chunk
            self.code_view.scroll_to_chunk(start_char, end_char)
            self.code_view.highlight_chunk(start_char, end_char)

            # Refresh display with updated current chunk marker
            if self.sources_list.currentRow() >= 0:
                self._on_source_selected(self.sources_list.currentRow())

        def _on_chunk_ctrl_clicked(self, chunk_index: int) -> None:
            """Handle Ctrl+click on a chunk marker for diff comparison."""
            if chunk_index not in self._chunk_content_map:
                return

            # Toggle selection (add or remove)
            if chunk_index in self._selected_chunks_for_diff:
                self._selected_chunks_for_diff.remove(chunk_index)
            else:
                # Keep max 2 chunks selected
                if len(self._selected_chunks_for_diff) >= 2:
                    self._selected_chunks_for_diff.pop(0)
                self._selected_chunks_for_diff.append(chunk_index)

            # Enable compare button if 2 chunks selected
            self.compare_button.setEnabled(len(self._selected_chunks_for_diff) == 2)

            # Update minimap to show selected chunks
            self.minimap.set_selected_for_diff(self._selected_chunks_for_diff)

        def _on_compare_chunks(self) -> None:
            """Show diff of the two selected chunks."""
            if len(self._selected_chunks_for_diff) != 2:
                QMessageBox.warning(
                    self, "Compare Chunks", "Please select exactly 2 chunks (Ctrl+Click)."
                )
                return

            chunk1_idx, chunk2_idx = self._selected_chunks_for_diff
            content1 = self._chunk_content_map.get(chunk1_idx, "")
            content2 = self._chunk_content_map.get(chunk2_idx, "")

            # Generate unified diff
            import difflib

            diff_lines = list(
                difflib.unified_diff(
                    content1.splitlines(keepends=True),
                    content2.splitlines(keepends=True),
                    fromfile=f"Chunk {chunk1_idx + 1}",
                    tofile=f"Chunk {chunk2_idx + 1}",
                    lineterm="",
                )
            )

            # Create diff view dialog
            diff_text = "".join(diff_lines)

            diff_dialog = DiffDialog(
                self,
                f"Comparing Chunk {chunk1_idx + 1} vs Chunk {chunk2_idx + 1}",
                diff_text,
                content1,
                content2,
            )
            diff_dialog.exec()

        def _on_export(self) -> None:
            """Export annotated file with chunk markers to disk."""
            if not self._current_source_path or not self._current_display_content:
                QMessageBox.warning(self, "Export", "No source file selected to export.")
                return

            # Get suggested filename with .annotated extension
            src_name = Path(self._current_source_path).name
            name_without_ext = Path(src_name).stem
            ext = Path(src_name).suffix
            suggested_filename = f"{name_without_ext}.annotated{ext}"

            # Open save dialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Annotated File",
                suggested_filename,
                "All Files (*);;Text Files (*.txt);;Python Files (*.py);;JavaScript Files (*.js)",
            )

            if not file_path:
                return

            try:
                # Write the annotated content to file
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self._current_display_content)

                QMessageBox.information(
                    self, "Export Successful", f"Annotated file saved to:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export file:\n{str(e)}")

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
                "[Index complete] " f"Files: {result.total_files}, chunks: {result.total_chunks}\n"
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
