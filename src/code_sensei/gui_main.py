"""
gui_main.py
-----------
Executable entrypoint for the desktop GUI build.

This module is used by PyInstaller to produce a standalone Windows EXE.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from code_sensei.gui.app import run_gui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch CodeSensei GUI")
    parser.add_argument(
        "--project-dir",
        "-p",
        default=".",
        help="Project directory to open initially.",
    )
    parser.add_argument(
        "--top-k",
        "-k",
        type=int,
        default=8,
        help="Chunks to retrieve for Q&A.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Start in retrieval-only mode.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.project_dir).resolve()
    return run_gui(project_dir=str(root), top_k=args.top_k, use_llm=not args.no_llm)


if __name__ == "__main__":
    raise SystemExit(main())
