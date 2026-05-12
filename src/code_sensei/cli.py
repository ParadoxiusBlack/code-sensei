"""
cli.py
------
CodeSensei command-line interface.

Entry point: ``code-sensei`` (defined in pyproject.toml).

Commands
~~~~~~~~
index   — Index (or re-index) a codebase directory.
ask     — Ask a natural-language question about the indexed codebase.
tests   — Generate tests for a file or module.
refactor — Analyse code for refactoring opportunities.
docs    — Generate documentation for a target.
chat    — Start an interactive multi-turn chat session.
status  — Show the current index statistics.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _warn_panel(message: str, hint: str | None = None) -> None:
    """Print a yellow warning panel to the console."""
    body = message if hint is None else f"{message}\n\n[dim]{hint}[/dim]"
    console.print(Panel(body, title="[bold yellow]Warning[/]", border_style="yellow", expand=False))


def _error_panel(message: str, hint: str | None = None) -> None:
    """Print a red error panel to the console."""
    body = message if hint is None else f"{message}\n\n[bold]{hint}[/bold]"
    console.print(Panel(body, title="[bold red]Error[/]", border_style="red", expand=False))


def _check_llm_status(assistant: object) -> None:
    """Emit a warning panel when the LLM could not be initialised."""
    err: str | None = getattr(assistant, "llm_init_error", None)
    if err:
        _warn_panel(
            "[yellow]LLM is not available — running in retrieval-only mode.[/yellow]",
            hint=err,
        )


def _check_embed_status(embedder: object) -> None:
    """Emit a warning panel when the embedding model could not be initialised."""
    err: str | None = getattr(embedder, "embed_init_error", None)
    if err:
        _warn_panel(
            "[yellow]Embedding model is not available — results may be empty.[/yellow]",
            hint=err,
        )


def _handle_vector_store_error(exc: Exception, collection: str) -> None:
    """Print an actionable error panel for ChromaDB dimension / collection errors."""
    from code_sensei.errors import VectorStoreDimensionError

    exc_lower = str(exc).lower()
    if "dimension" in exc_lower or "dimensionality" in exc_lower:
        dim_err = VectorStoreDimensionError(collection)
        _error_panel(str(dim_err), hint=dim_err.hint)
    else:
        _error_panel(f"Vector store error: {exc}")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s — %(name)s — %(message)s")


def _load_pipeline(project_dir: Path):
    """
    Build and return the shared (vector_store, embedder, retriever) triple.

    Kept in a helper so each sub-command can share the same setup logic.
    Raises ``SystemExit`` on unrecoverable vector-store errors.
    """
    from code_sensei.indexer.embedder import Embedder
    from code_sensei.retrieval.retriever import Retriever
    from code_sensei.retrieval.vector_store import VectorStore

    collection = _collection_name_for_project(project_dir)
    vector_store = VectorStore(collection_name=collection)
    try:
        vector_store.connect()
    except Exception as exc:
        _handle_vector_store_error(exc, collection)
        sys.exit(1)

    embedder = Embedder()
    _check_embed_status(embedder)
    retriever = Retriever(vector_store=vector_store, embedder=embedder)
    return vector_store, embedder, retriever


def _sanitize_collection_part(value: str) -> str:
    """Convert provider/model names into a stable Chroma-safe token."""
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_").lower() or "default"


def _collection_name_for_project(project_dir: Path) -> str:
    """Derive collection name from project + embedding config to avoid dim collisions."""
    project_name = project_dir.name or "code_sensei_default"
    try:
        from config.settings import EMBEDDING_MODEL, EMBEDDING_PROVIDER
    except ImportError:
        EMBEDDING_MODEL = "nomic-embed-text"
        EMBEDDING_PROVIDER = "ollama"

    provider = _sanitize_collection_part(EMBEDDING_PROVIDER)
    model = _sanitize_collection_part(EMBEDDING_MODEL)
    return f"{project_name}__{provider}__{model}"


# ---------------------------------------------------------------------------
# Root command group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="code-sensei")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """
    \b
    ╔═══════════════════════════════════════╗
    ║   CodeSensei — Local Codebase LLM    ║
    ╚═══════════════════════════════════════╝
    RAG-powered assistant for your codebase.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    _setup_logging(verbose)


# ---------------------------------------------------------------------------
# index
# ---------------------------------------------------------------------------


@main.command()
@click.argument("project_dir", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("--extensions", "-e", multiple=True, help="Extra file extensions to index.")
@click.pass_context
def index(ctx: click.Context, project_dir: str, extensions: tuple[str, ...]) -> None:
    """Index (or re-index) a codebase directory."""
    root = Path(project_dir).resolve()
    console.print(Panel(f"[bold cyan]Indexing[/] [green]{root}[/]", expand=False))

    from code_sensei.indexer.chunker import Chunker
    from code_sensei.indexer.embedder import Embedder
    from code_sensei.indexer.file_loader import FileLoader
    from code_sensei.retrieval.vector_store import VectorStore

    extra_exts = set(extensions) if extensions else None
    loader = FileLoader(root=root, extensions=extra_exts)
    chunker = Chunker()
    embedder = Embedder()
    _check_embed_status(embedder)
    collection = _collection_name_for_project(root)
    vector_store = VectorStore(collection_name=collection)
    vector_store.connect()

    total_files = 0
    total_chunks = 0

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Loading and indexing files…", total=None)

            for source_file in loader.load():
                total_files += 1
                progress.update(task, description=f"Indexing [cyan]{source_file.path.name}[/]…")
                chunks = chunker.chunk_file(source_file)
                embedded = embedder.embed_chunks(chunks)
                vector_store.upsert(embedded)
                total_chunks += len(chunks)
    except Exception as exc:
        _handle_vector_store_error(exc, collection)
        sys.exit(1)

    console.print(
        f"\n[green]✓[/] Indexed [bold]{total_files}[/] files, "
        f"[bold]{total_chunks}[/] chunks into collection [cyan]'{collection}'[/].\n"
    )


# ---------------------------------------------------------------------------
# ask
# ---------------------------------------------------------------------------


@main.command()
@click.argument("question")
@click.option(
    "--project-dir", "-p", default=".", type=click.Path(exists=True, file_okay=False),
    help="Project directory (used to resolve the vector-store collection).",
)
@click.option("--top-k", "-k", default=8, show_default=True, help="Chunks to retrieve.")
@click.option("--language", "-l", default=None, help="Filter by language.")
@click.option("--no-llm", is_flag=True, help="Show raw chunks without LLM summary.")
@click.option("--stream/--no-stream", default=True, show_default=True, help="Stream answer output.")
@click.pass_context
def ask(
    ctx: click.Context,
    question: str,
    project_dir: str,
    top_k: int,
    language: str | None,
    no_llm: bool,
    stream: bool,
) -> None:
    """Ask a natural-language question about the indexed codebase."""
    root = Path(project_dir).resolve()

    from code_sensei.assistant.qa import CodeQA

    _, _, retriever = _load_pipeline(root)
    qa = CodeQA(retriever=retriever, top_k=top_k)
    _check_llm_status(qa)

    if stream:
        stream_iter, sources, _ = qa.ask_stream(
            question=question,
            language_filter=language,
            use_llm=not no_llm,
        )
        parts: list[str] = []
        console.print("[bold]Answer[/]")
        for piece in stream_iter:
            console.print(piece, end="")
            parts.append(piece)
        console.print("")
        response_answer = "".join(parts)
    else:
        with console.status("[bold cyan]Thinking…[/]"):
            response = qa.ask(question=question, language_filter=language, use_llm=not no_llm)
        console.print(Panel(Markdown(response.answer), title="[bold]Answer[/]", expand=False))
        sources = response.sources
        response_answer = response.answer

    if stream and not response_answer.strip():
        console.print("[dim]No response text returned.[/]")

    if sources:
        console.print("\n[dim]Sources:[/]")
        for src in sources:
            console.print(f"  [cyan]{src}[/]")


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@main.command("tests")
@click.argument("target")
@click.option(
    "--project-dir", "-p", default=".", type=click.Path(exists=True, file_okay=False),
)
@click.option(
    "--framework", "-f", default="pytest", show_default=True,
    help="Test framework (pytest, jest, junit, …).",
)
@click.option(
    "--output", "-o", default=None, type=click.Path(),
    help="Write generated tests to this file.",
)
@click.pass_context
def generate_tests(
    ctx: click.Context,
    target: str,
    project_dir: str,
    framework: str,
    output: str | None,
) -> None:
    """Generate unit / integration tests for a file or module."""
    root = Path(project_dir).resolve()

    from code_sensei.assistant.test_generator import TestGenerator

    _, _, retriever = _load_pipeline(root)
    gen = TestGenerator(retriever=retriever)
    _check_llm_status(gen)

    with console.status(f"[bold cyan]Generating {framework} tests for {target}…[/]"):
        result = gen.generate(target=target, framework=framework)

    if output:
        Path(output).write_text(result.test_code)
        console.print(f"[green]✓[/] Tests written to [cyan]{output}[/].")
    else:
        console.print(Panel(Markdown(f"```python\n{result.test_code}\n```"), title="Generated Tests"))


# ---------------------------------------------------------------------------
# refactor
# ---------------------------------------------------------------------------


@main.command()
@click.argument("target")
@click.option(
    "--project-dir", "-p", default=".", type=click.Path(exists=True, file_okay=False),
)
@click.option("--language", "-l", default=None, help="Filter by language.")
@click.pass_context
def refactor(
    ctx: click.Context,
    target: str,
    project_dir: str,
    language: str | None,
) -> None:
    """Analyse code for refactoring opportunities."""
    root = Path(project_dir).resolve()

    from code_sensei.assistant.refactor import RefactorAdvisor

    _, _, retriever = _load_pipeline(root)
    advisor = RefactorAdvisor(retriever=retriever)
    _check_llm_status(advisor)

    with console.status("[bold cyan]Analysing code…[/]"):
        report = advisor.analyse(target=target, language_filter=language)

    console.print(Panel(Markdown(report.raw_response), title="[bold]Refactor Report[/]"))


# ---------------------------------------------------------------------------
# docs
# ---------------------------------------------------------------------------


@main.command()
@click.argument("target")
@click.option(
    "--project-dir", "-p", default=".", type=click.Path(exists=True, file_okay=False),
)
@click.option(
    "--type", "doc_type", default="docstrings", show_default=True,
    type=click.Choice(["docstrings", "readme", "architecture", "api_reference"]),
    help="Type of documentation to generate.",
)
@click.option(
    "--style", default="google", show_default=True,
    type=click.Choice(["google", "numpy", "sphinx", "markdown"]),
)
@click.option("--output", "-o", default=None, type=click.Path())
@click.pass_context
def docs(
    ctx: click.Context,
    target: str,
    project_dir: str,
    doc_type: str,
    style: str,
    output: str | None,
) -> None:
    """Generate documentation for a file, module, or the entire project."""
    root = Path(project_dir).resolve()

    from code_sensei.assistant.doc_generator import DocGenerator

    _, _, retriever = _load_pipeline(root)
    gen = DocGenerator(retriever=retriever)
    _check_llm_status(gen)

    with console.status(f"[bold cyan]Generating {doc_type} documentation…[/]"):
        result = gen.generate(target=target, doc_type=doc_type, style=style)

    if output:
        Path(output).write_text(result.content)
        console.print(f"[green]✓[/] Documentation written to [cyan]{output}[/].")
    else:
        console.print(Panel(Markdown(result.content), title="[bold]Documentation[/]"))


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--project-dir", "-p", default=".", type=click.Path(exists=True, file_okay=False),
)
@click.option(
    "--session-id", "-s", default="default", show_default=True,
    help="Session ID for persistent conversation memory.",
)
@click.option(
    "--no-llm", is_flag=True, help="Start in retrieval-only mode (no LLM)."
)
@click.option("--stream/--no-stream", default=True, show_default=True, help="Stream answer output.")
@click.pass_context
def chat(ctx: click.Context, project_dir: str, session_id: str, no_llm: bool, stream: bool) -> None:
    """Start an interactive multi-turn chat session."""
    root = Path(project_dir).resolve()

    from code_sensei.assistant.qa import CodeQA
    from code_sensei.cache.sqlite_cache import SqliteCache
    from code_sensei.memory.conversation import ConversationMemory

    _, _, retriever = _load_pipeline(root)
    cache = SqliteCache()
    memory = ConversationMemory(session_id=session_id, cache=cache)
    qa = CodeQA(retriever=retriever)
    _check_llm_status(qa)

    # Track whether to use LLM
    use_llm = not no_llm

    console.print(
        Panel(
            "[bold cyan]CodeSensei Chat[/]\n"
            "Type your question and press Enter.  "
            "Type [bold]exit[/] or [bold]quit[/] to leave.  "
            "Type [bold]/clear[/] to reset memory.\n"
            f"Type [bold]/llm-off[/] or [bold]/llm-on[/] to toggle LLM mode. "
            f"(Currently: {'LLM enabled' if use_llm else 'Retrieval-only'}, "
            f"{'streaming on' if stream else 'streaming off'})",
            expand=False,
        )
    )

    while True:
        try:
            question = console.input("[bold green]You:[/] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Bye![/]")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            console.print("[dim]Bye![/]")
            break
        if question == "/clear":
            memory.clear()
            console.print("[dim]Conversation memory cleared.[/]")
            continue
        if question == "/llm-off":
            use_llm = False
            console.print("[dim]Switched to retrieval-only mode (no LLM).[/]")
            continue
        if question == "/llm-on":
            use_llm = True
            console.print("[dim]Switched to LLM mode.[/]")
            continue
        if question == "/stream-off":
            stream = False
            console.print("[dim]Switched streaming off.[/]")
            continue
        if question == "/stream-on":
            stream = True
            console.print("[dim]Switched streaming on.[/]")
            continue

        memory.add_user_message(question)
        if stream:
            stream_iter, _, _ = qa.ask_stream(question=question, use_llm=use_llm)
            parts: list[str] = []
            console.print("[bold cyan]CodeSensei:[/] ", end="")
            for piece in stream_iter:
                console.print(piece, end="")
                parts.append(piece)
            console.print("")
            answer = "".join(parts)
        else:
            with console.status("[bold cyan]Thinking…[/]"):
                response = qa.ask(question=question, use_llm=use_llm)
            answer = response.answer
            console.print(Panel(Markdown(answer), title="[bold]CodeSensei[/]", expand=False))

        memory.add_assistant_message(answer)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@main.command()
@click.option(
    "--project-dir", "-p", default=".", type=click.Path(exists=True, file_okay=False),
)
@click.pass_context
def status(ctx: click.Context, project_dir: str) -> None:
    """Show index statistics for the project."""
    root = Path(project_dir).resolve()

    from code_sensei.retrieval.vector_store import VectorStore

    collection = _collection_name_for_project(root)
    vs = VectorStore(collection_name=collection)
    vs.connect()

    count = vs.count()

    table = Table(title="CodeSensei Index Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="bold")
    table.add_row("Project directory", str(root))
    table.add_row("Collection", collection)
    table.add_row("Indexed chunks", str(count))
    console.print(table)


# ---------------------------------------------------------------------------
# watch (start file watcher for auto re-indexing)
# ---------------------------------------------------------------------------


@main.command()
@click.argument("project_dir", default=".", type=click.Path(exists=True, file_okay=False))
@click.pass_context
def watch(ctx: click.Context, project_dir: str) -> None:
    """Watch a codebase directory and auto-reindex on file changes."""
    import time

    root = Path(project_dir).resolve()
    console.print(Panel(f"[bold cyan]Watching[/] [green]{root}[/] for changes…", expand=False))

    from code_sensei.indexer.chunker import Chunker
    from code_sensei.indexer.embedder import Embedder
    from code_sensei.indexer.file_loader import FileLoader
    from code_sensei.indexer.watcher import CodebaseWatcher
    from code_sensei.retrieval.vector_store import VectorStore

    embedder = Embedder()
    chunker = Chunker()
    collection = _collection_name_for_project(root)
    vector_store = VectorStore(collection_name=collection)
    vector_store.connect()
    loader = FileLoader(root=root)

    def _on_change(event_type: str, path: Path) -> None:
        console.print(f"[cyan]{event_type.upper()}[/] {path}")
        if event_type == "deleted":
            vector_store.delete_by_source(str(path))
        else:
            source_file = loader.load_single(path)
            if source_file:
                chunks = chunker.chunk_file(source_file)
                embedded = embedder.embed_chunks(chunks)
                vector_store.upsert(embedded)
                console.print(f"  [green]✓[/] Re-indexed {len(chunks)} chunks.")

    with CodebaseWatcher(root=root, on_change=_on_change):
        console.print("[dim]Press Ctrl+C to stop.[/]")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[dim]Watcher stopped.[/]")


if __name__ == "__main__":
    main()
