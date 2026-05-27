"""
indexer/file_loader.py
----------------------
Walks a codebase directory tree and returns source-code files as
structured ``SourceFile`` objects, ready for the chunking pipeline.

Design notes
~~~~~~~~~~~~
* Skips directories listed in ``DEFAULT_IGNORE_DIRS`` and files whose
  extension is not in ``DEFAULT_SOURCE_EXTENSIONS``.
* Returns a generator so the caller can stream files without loading
  the entire codebase into memory at once.
* Binary files are silently skipped (detected via ``chardet`` or a
  lightweight heuristic).
"""

from __future__ import annotations

import logging
from collections.abc import Generator, Iterable
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from types import ModuleType

import chardet

# Allow the module to be imported standalone (outside the installed package).
try:
    _settings: ModuleType | None = import_module("config.settings")
except ImportError:
    _settings = None

DEFAULT_SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    getattr(_settings, "DEFAULT_SOURCE_EXTENSIONS", frozenset({".py", ".js", ".ts", ".md"}))
)
DEFAULT_IGNORE_DIRS: frozenset[str] = frozenset(
    getattr(
        _settings, "DEFAULT_IGNORE_DIRS", {"__pycache__", ".git", "node_modules", ".venv", "venv"}
    )
)
DEFAULT_IGNORE_FILES: frozenset[str] = frozenset(
    getattr(_settings, "DEFAULT_IGNORE_FILES", frozenset())
)

logger = logging.getLogger(__name__)


@dataclass
class SourceFile:
    """A single source file with its content and metadata."""

    path: Path
    content: str
    language: str = ""
    encoding: str = "utf-8"
    size_bytes: int = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.language:
            self.language = _infer_language(self.path)
        if not self.size_bytes:
            self.size_bytes = len(self.content.encode("utf-8", errors="replace"))


def _infer_language(path: Path) -> str:
    """Return a human-readable language name based on file extension."""
    _MAP: dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".java": "java",
        ".kt": "kotlin",
        ".go": "go",
        ".rb": "ruby",
        ".rs": "rust",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".php": "php",
        ".swift": "swift",
        ".scala": "scala",
        ".sh": "bash",
        ".bash": "bash",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".json": "json",
        ".md": "markdown",
        ".rst": "rst",
    }
    return _MAP.get(path.suffix.lower(), "text")


def _is_likely_binary(raw: bytes) -> bool:
    """Heuristic: if more than 30 % of the first 8 kB are non-printable bytes, treat as binary."""
    sample = raw[:8192]
    if not sample:
        return False
    non_printable = sum(1 for b in sample if b < 9 or (14 <= b < 32 and b != 27))
    return non_printable / len(sample) > 0.30


class FileLoader:
    """
    Recursively loads source files from a directory.

    Parameters
    ----------
    root:
        Root directory of the codebase to index.
    extensions:
        Allowed file extensions (including the leading dot, e.g. ``".py"``).
        Defaults to ``DEFAULT_SOURCE_EXTENSIONS``.
    ignore_dirs:
        Directory names to skip during traversal.
        Defaults to ``DEFAULT_IGNORE_DIRS``.
    """

    def __init__(
        self,
        root: str | Path,
        extensions: Iterable[str] | None = None,
        ignore_dirs: Iterable[str] | None = None,
        ignore_files: Iterable[str] | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.extensions: frozenset[str] = (
            frozenset(extensions) if extensions is not None else DEFAULT_SOURCE_EXTENSIONS
        )
        self.ignore_dirs: frozenset[str] = (
            frozenset(ignore_dirs) if ignore_dirs is not None else DEFAULT_IGNORE_DIRS
        )
        self.ignore_files: frozenset[str] = (
            frozenset(ignore_files) if ignore_files is not None else DEFAULT_IGNORE_FILES
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> Generator[SourceFile, None, None]:
        """Yield ``SourceFile`` objects for every discovered source file."""
        if not self.root.is_dir():
            raise ValueError(f"Root path is not a directory: {self.root}")

        for file_path in self._walk():
            source_file = self._read_file(file_path)
            if source_file is not None:
                yield source_file

    def load_single(self, path: str | Path) -> SourceFile | None:
        """Load (and return) a single file. Returns ``None`` if unreadable."""
        return self._read_file(Path(path))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _walk(self) -> Generator[Path, None, None]:
        """Recursively yield file paths, skipping ignored dirs & extensions."""
        for item in self.root.rglob("*"):
            if not item.is_file():
                continue
            # Skip paths that contain an ignored directory component.
            if any(part in self.ignore_dirs for part in item.parts):
                continue
            if item.name in self.ignore_files:
                continue
            if item.suffix.lower() in self.extensions:
                yield item

    def _read_file(self, path: Path) -> SourceFile | None:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            logger.warning("Cannot read %s: %s", path, exc)
            return None

        if _is_likely_binary(raw):
            logger.debug("Skipping binary file: %s", path)
            return None

        # Detect encoding.
        detected = chardet.detect(raw)
        encoding = detected.get("encoding") or "utf-8"
        try:
            content = raw.decode(encoding, errors="replace")
        except (LookupError, UnicodeDecodeError):
            content = raw.decode("utf-8", errors="replace")
            encoding = "utf-8"

        return SourceFile(
            path=path,
            content=content,
            encoding=encoding,
            metadata={"relative_path": str(path.relative_to(self.root))},
        )
