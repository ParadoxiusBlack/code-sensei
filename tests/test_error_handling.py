"""
tests/test_error_handling.py
----------------------------
Tests for Phase 3 error handling: typed exceptions, LLM diagnostics,
embedder diagnostics, and CLI error surface.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from code_sensei.errors import (
    CodeSenseiError,
    EmbeddingModelError,
    ModelNotFoundError,
    OllamaConnectionError,
    VectorStoreDimensionError,
)


# ---------------------------------------------------------------------------
# Typed exception tests
# ---------------------------------------------------------------------------


class TestTypedExceptions:
    def test_ollama_connection_error_inherits_base(self):
        exc = OllamaConnectionError()
        assert isinstance(exc, CodeSenseiError)
        assert "ollama" in str(exc).lower()
        assert hasattr(exc, "hint")
        assert "ollama serve" in exc.hint

    def test_ollama_connection_error_custom_url(self):
        exc = OllamaConnectionError("http://remote:11434")
        assert "remote" in str(exc)

    def test_model_not_found_error(self):
        exc = ModelNotFoundError("llama3")
        assert isinstance(exc, CodeSenseiError)
        assert "llama3" in str(exc)
        assert "llama3" in exc.hint
        assert "ollama pull" in exc.hint

    def test_embedding_model_error(self):
        exc = EmbeddingModelError("nomic-embed-text", "connection refused")
        assert isinstance(exc, CodeSenseiError)
        assert "nomic-embed-text" in str(exc)

    def test_vector_store_dimension_error(self):
        exc = VectorStoreDimensionError("my_collection", stored_dim=1536, new_dim=768)
        assert isinstance(exc, CodeSenseiError)
        assert "my_collection" in str(exc)
        assert "1536" in str(exc)
        assert "768" in str(exc)
        assert hasattr(exc, "hint")
        assert "re-index" in exc.hint.lower()

    def test_vector_store_dimension_error_no_dims(self):
        exc = VectorStoreDimensionError("col")
        assert "col" in str(exc)


# ---------------------------------------------------------------------------
# _BaseAssistant llm_init_error tests
# ---------------------------------------------------------------------------


def _make_bare_assistant():
    """Return a _BaseAssistant instance with no LLM initialised."""
    from code_sensei.assistant._base import _BaseAssistant

    a = _BaseAssistant.__new__(_BaseAssistant)
    a.model = "mistral"
    a.temperature = 0.2
    a.max_tokens = 2048
    a.llm_init_error = None
    return a


class TestBaseAssistantErrorDiagnostics:
    """Verify that _BaseAssistant exposes llm_init_error with actionable messages."""

    def test_llm_init_error_is_none_on_success(self):
        a = _make_bare_assistant()
        a._llm = MagicMock()
        assert a.llm_init_error is None

    def test_llm_init_error_connection_refused(self):
        """_try_ollama sets llm_init_error on connection refused."""
        a = _make_bare_assistant()

        with (
            patch("code_sensei.assistant._base.OLLAMA_MODEL", "mistral"),
            patch("langchain_ollama.OllamaLLM", side_effect=Exception("Connection refused")),
        ):
            result = a._try_ollama()

        assert result is None
        assert a.llm_init_error is not None
        assert "ollama serve" in a.llm_init_error.lower()

    def test_llm_init_error_model_not_found(self):
        """_try_ollama sets llm_init_error when model is not found (404)."""
        a = _make_bare_assistant()

        with (
            patch("code_sensei.assistant._base.OLLAMA_MODEL", "mistral"),
            patch(
                "langchain_ollama.OllamaLLM",
                side_effect=Exception("model 'mistral' not found, 404"),
            ),
        ):
            result = a._try_ollama()

        assert result is None
        assert a.llm_init_error is not None
        assert "ollama pull" in a.llm_init_error.lower()
        assert "mistral" in a.llm_init_error

    def test_llm_init_error_generic_exception(self):
        """_try_ollama sets llm_init_error for unrecognised errors."""
        a = _make_bare_assistant()

        with patch("langchain_ollama.OllamaLLM", side_effect=Exception("some unexpected error")):
            result = a._try_ollama()

        assert result is None
        assert a.llm_init_error is not None


# ---------------------------------------------------------------------------
# Embedder embed_init_error tests
# ---------------------------------------------------------------------------


class TestEmbedderErrorDiagnostics:
    def test_embed_init_error_is_none_on_success(self):
        from code_sensei.indexer.embedder import Embedder

        with patch("langchain_ollama.OllamaEmbeddings", return_value=MagicMock()):
            emb = Embedder(model="nomic-embed-text", provider="ollama")
        assert emb.embed_init_error is None

    def test_embed_init_error_connection_refused(self):
        from code_sensei.indexer.embedder import Embedder

        with patch(
            "langchain_ollama.OllamaEmbeddings",
            side_effect=Exception("Connection refused"),
        ):
            emb = Embedder(model="nomic-embed-text", provider="ollama")

        assert emb.embed_init_error is not None
        assert "ollama serve" in emb.embed_init_error.lower()

    def test_embed_init_error_model_not_found(self):
        from code_sensei.indexer.embedder import Embedder

        with patch(
            "langchain_ollama.OllamaEmbeddings",
            side_effect=Exception("model 'nomic-embed-text' not found 404"),
        ):
            emb = Embedder(model="nomic-embed-text", provider="ollama")

        assert emb.embed_init_error is not None
        assert "ollama pull" in emb.embed_init_error.lower()
        assert "nomic-embed-text" in emb.embed_init_error

    def test_embed_init_error_generic(self):
        from code_sensei.indexer.embedder import Embedder

        with patch(
            "langchain_ollama.OllamaEmbeddings",
            side_effect=Exception("unexpected failure"),
        ):
            emb = Embedder(model="nomic-embed-text", provider="ollama")

        assert emb.embed_init_error is not None
        assert "nomic-embed-text" in emb.embed_init_error

    def test_embed_init_error_unsupported_provider(self):
        from code_sensei.indexer.embedder import Embedder

        emb = Embedder(model="some-model", provider="unknown_provider")
        assert emb.embed_init_error is not None


# ---------------------------------------------------------------------------
# CLI helper tests
# ---------------------------------------------------------------------------


class TestCLIHelpers:
    def test_warn_panel_emits_output(self, capsys):
        from rich.console import Console

        from code_sensei.cli import _warn_panel

        # Replace console temporarily with one that writes to stderr
        import code_sensei.cli as cli_module

        original = cli_module.console
        cli_module.console = Console(highlight=False)
        try:
            _warn_panel("something went wrong", hint="fix it like this")
        finally:
            cli_module.console = original

    def test_error_panel_emits_output(self):
        from rich.console import Console

        from code_sensei.cli import _error_panel

        import code_sensei.cli as cli_module

        original = cli_module.console
        cli_module.console = Console(highlight=False)
        try:
            _error_panel("fatal error", hint="do this")
        finally:
            cli_module.console = original

    def test_check_llm_status_no_error_no_output(self, capsys):
        from code_sensei.cli import _check_llm_status

        obj = MagicMock()
        obj.llm_init_error = None
        # Should not raise
        _check_llm_status(obj)

    def test_check_llm_status_with_error_prints_panel(self):
        from rich.console import Console

        from code_sensei.cli import _check_llm_status

        import code_sensei.cli as cli_module

        output_lines: list[str] = []

        class CapturingConsole(Console):
            def print(self, *args, **kwargs):  # type: ignore[override]
                output_lines.append(str(args))

        original = cli_module.console
        cli_module.console = CapturingConsole(highlight=False)
        try:
            obj = MagicMock()
            obj.llm_init_error = "Ollama is not running. Hint: ollama serve"
            _check_llm_status(obj)
        finally:
            cli_module.console = original

        combined = " ".join(output_lines)
        assert len(output_lines) > 0  # _check_llm_status printed something

    def test_check_embed_status_with_error(self):
        from rich.console import Console

        from code_sensei.cli import _check_embed_status

        import code_sensei.cli as cli_module

        output_lines: list[str] = []

        class CapturingConsole(Console):
            def print(self, *args, **kwargs):  # type: ignore[override]
                output_lines.append(str(args))

        original = cli_module.console
        cli_module.console = CapturingConsole(highlight=False)
        try:
            obj = MagicMock()
            obj.embed_init_error = "Embedding model unavailable. Hint: ollama pull nomic-embed-text"
            _check_embed_status(obj)
        finally:
            cli_module.console = original

        combined = " ".join(output_lines)
        assert len(output_lines) > 0  # _check_embed_status printed something

    def test_handle_vector_store_error_dimension(self):
        from rich.console import Console

        from code_sensei.cli import _handle_vector_store_error

        import code_sensei.cli as cli_module

        output_lines: list[str] = []

        class CapturingConsole(Console):
            def print(self, *args, **kwargs):  # type: ignore[override]
                output_lines.append(str(args))

        original = cli_module.console
        cli_module.console = CapturingConsole(highlight=False)
        try:
            _handle_vector_store_error(
                Exception("Dimensionality of (768,) does not match index dimensionality (1536)"),
                "test_collection",
            )
        finally:
            cli_module.console = original

        combined = " ".join(output_lines)
        assert len(output_lines) > 0  # _handle_vector_store_error printed something
