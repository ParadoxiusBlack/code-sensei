"""
indexer/watcher.py
------------------
Watches a codebase directory for file changes and triggers incremental
re-indexing via a callback.

Design notes
~~~~~~~~~~~~
* Built on top of the ``watchdog`` library.
* The ``CodebaseWatcher`` is intentionally decoupled from the indexing
  pipeline: it calls a user-supplied ``on_change`` callback with the
  affected file path, allowing callers to decide how to handle the event
  (full re-index, single-file update, etc.).
* Only events matching the configured source extensions are forwarded.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

try:
    from config.settings import DEFAULT_SOURCE_EXTENSIONS
except ImportError:
    DEFAULT_SOURCE_EXTENSIONS = frozenset({".py", ".js", ".ts", ".md"})

logger = logging.getLogger(__name__)

# Type alias for the callback: receives (event_type, file_path)
ChangeCallback = Callable[[str, Path], None]


class CodebaseWatcher:
    """
    Monitors a directory for source-file changes and invokes a callback.

    Parameters
    ----------
    root:
        Root directory to watch.
    on_change:
        Callable invoked with ``(event_type, path)`` on every relevant event.
        ``event_type`` is one of ``"created"``, ``"modified"``, ``"deleted"``.
    extensions:
        File extensions to watch.  Defaults to ``DEFAULT_SOURCE_EXTENSIONS``.
    recursive:
        Whether to watch sub-directories recursively.
    """

    def __init__(
        self,
        root: str | Path,
        on_change: ChangeCallback,
        extensions: frozenset[str] | None = None,
        recursive: bool = True,
    ) -> None:
        self.root = Path(root).resolve()
        self.on_change = on_change
        self.extensions = extensions or DEFAULT_SOURCE_EXTENSIONS
        self.recursive = recursive
        self._observer = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the file-system observer in a background thread."""
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            handler = _ChangeHandler(
                on_change=self.on_change, extensions=self.extensions
            )
            observer = Observer()
            observer.schedule(handler, str(self.root), recursive=self.recursive)
            observer.start()
            self._observer = observer
            logger.info("CodebaseWatcher started on: %s", self.root)
        except ImportError:
            logger.warning(
                "watchdog is not installed; file-system watching is disabled. "
                "Run `pip install watchdog` to enable."
            )

    def stop(self) -> None:
        """Stop the background observer gracefully."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.info("CodebaseWatcher stopped.")

    def __enter__(self) -> "CodebaseWatcher":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()


# ---------------------------------------------------------------------------
# Internal event handler
# ---------------------------------------------------------------------------


class _ChangeHandler:
    """
    Watchdog event handler that forwards relevant events to the callback.

    Inherits from ``FileSystemEventHandler`` lazily so the class can be
    defined even if ``watchdog`` is not installed.
    """

    def __init__(self, on_change: ChangeCallback, extensions: frozenset[str]) -> None:
        self.on_change = on_change
        self.extensions = extensions
        # Lazily inherit if watchdog is available.
        try:
            from watchdog.events import FileSystemEventHandler

            _ChangeHandler.__bases__ = (FileSystemEventHandler,)
        except ImportError:
            pass

    def _is_relevant(self, path: str) -> bool:
        return Path(path).suffix.lower() in self.extensions

    def on_created(self, event) -> None:  # type: ignore[override]
        if not event.is_directory and self._is_relevant(event.src_path):
            logger.debug("File created: %s", event.src_path)
            self.on_change("created", Path(event.src_path))

    def on_modified(self, event) -> None:  # type: ignore[override]
        if not event.is_directory and self._is_relevant(event.src_path):
            logger.debug("File modified: %s", event.src_path)
            self.on_change("modified", Path(event.src_path))

    def on_deleted(self, event) -> None:  # type: ignore[override]
        if not event.is_directory and self._is_relevant(event.src_path):
            logger.debug("File deleted: %s", event.src_path)
            self.on_change("deleted", Path(event.src_path))
