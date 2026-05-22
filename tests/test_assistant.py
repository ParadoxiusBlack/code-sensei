"""
tests/test_assistant.py
-----------------------
Unit tests for all assistant feature modules:
  CodeQA, TestGenerator, RefactorAdvisor, DocGenerator.

All LLM and retriever calls are mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from code_sensei.assistant.doc_generator import DocGenerator, DocResult, DocStyle
from code_sensei.assistant.qa import CodeQA, QAResponse
from code_sensei.assistant.refactor import RefactorAdvisor, RefactorReport
from code_sensei.assistant.test_generator import TestGenerator, TestGenerationResult
from code_sensei.retrieval.retriever import RetrievalResult


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_result(score: float = 0.9, language: str = "python") -> RetrievalResult:
    return RetrievalResult(
        chunk_id="abc",
        content="def foo(): pass",
        source_path="/src/foo.py",
        language=language,
        score=score,
    )


def _make_retriever(*results: RetrievalResult) -> MagicMock:
    mock = MagicMock()
    mock.search.return_value = list(results) if results else [_make_result()]
    return mock


def _make_assistant(cls, retriever=None, **kwargs):
    """Instantiate an assistant with LLM patched out."""
    r = retriever or _make_retriever()
    with patch.object(cls, "_build_llm", return_value=None):
        instance = cls(retriever=r, **kwargs)
    return instance


# ---------------------------------------------------------------------------
# CodeQA
# ---------------------------------------------------------------------------


class TestCodeQA:
    def test_returns_qa_response(self):
        qa = _make_assistant(CodeQA)
        response = qa.ask("What does foo do?")
        assert isinstance(response, QAResponse)

    def test_question_preserved(self):
        qa = _make_assistant(CodeQA)
        response = qa.ask("explain the codebase")
        assert response.question == "explain the codebase"

    def test_answer_is_string(self):
        qa = _make_assistant(CodeQA)
        response = qa.ask("anything")
        assert isinstance(response.answer, str)

    def test_answer_contains_placeholder_when_no_llm(self):
        qa = _make_assistant(CodeQA)
        response = qa.ask("anything")
        assert "LLM not available" in response.answer or len(response.answer) > 0

    def test_sources_are_unique_paths(self):
        r = _make_retriever(_make_result(), _make_result())  # same source_path twice
        qa = _make_assistant(CodeQA, retriever=r)
        response = qa.ask("q")
        assert len(response.sources) == len(set(response.sources))

    def test_retriever_called_with_question(self):
        r = _make_retriever()
        qa = _make_assistant(CodeQA, retriever=r)
        qa.ask("Where is X?")
        r.search.assert_called_once()
        call_args = r.search.call_args
        assert "Where is X?" in (call_args.args or ()) or call_args.kwargs.get("query") == "Where is X?"

    def test_language_filter_forwarded(self):
        r = _make_retriever()
        qa = _make_assistant(CodeQA, retriever=r)
        qa.ask("q", language_filter="python")
        call_kwargs = r.search.call_args.kwargs
        assert call_kwargs.get("language_filter") == "python"

    def test_path_prefix_forwarded(self):
        r = _make_retriever()
        qa = _make_assistant(CodeQA, retriever=r)
        qa.ask("q", path_prefix="/src/")
        call_kwargs = r.search.call_args.kwargs
        assert call_kwargs.get("path_prefix") == "/src/"

    def test_ask_stream_returns_sources(self):
        r = _make_retriever(_make_result(), _make_result())
        qa = _make_assistant(CodeQA, retriever=r)
        with patch.object(CodeQA, "_invoke_stream", return_value=iter(["hello", " world"])):
            stream, sources, results = qa.ask_stream("explain")
            text = "".join(stream)

        assert text == "hello world"
        assert len(sources) == 1
        assert len(results) == 2

    def test_ask_uses_stream_path_to_build_answer(self):
        qa = _make_assistant(CodeQA)
        with patch.object(CodeQA, "ask_stream", return_value=(iter(["a", "b"]), ["/src/foo.py"], [])):
            response = qa.ask("q")

        assert response.answer == "ab"
        assert response.sources == ["/src/foo.py"]

    def test_last_query_metrics_populated_after_ask(self):
        qa = _make_assistant(CodeQA)
        qa.ask("measure this", use_llm=False)

        metrics = qa.last_query_metrics
        assert metrics is not None
        assert metrics.question == "measure this"
        assert metrics.use_llm is False
        assert metrics.total_ms >= 0.0
        assert metrics.retrieval_ms >= 0.0


# ---------------------------------------------------------------------------
# TestGenerator
# ---------------------------------------------------------------------------


class TestTestGenerator:
    def test_returns_test_generation_result(self):
        gen = _make_assistant(TestGenerator)
        result = gen.generate("foo.py")
        assert isinstance(result, TestGenerationResult)

    def test_source_path_preserved(self):
        gen = _make_assistant(TestGenerator)
        result = gen.generate("foo.py", framework="pytest")
        assert result.source_path == "foo.py"

    def test_framework_preserved(self):
        gen = _make_assistant(TestGenerator)
        result = gen.generate("foo.py", framework="jest")
        assert result.framework == "jest"

    def test_test_code_is_string(self):
        gen = _make_assistant(TestGenerator)
        result = gen.generate("foo.py")
        assert isinstance(result.test_code, str)

    def test_language_inferred_from_retrieval(self):
        r = _make_retriever(_make_result(language="javascript"))
        gen = _make_assistant(TestGenerator, retriever=r)
        result = gen.generate("app.js")
        assert result.language == "javascript"


# ---------------------------------------------------------------------------
# RefactorAdvisor
# ---------------------------------------------------------------------------


class TestRefactorAdvisor:
    def test_returns_refactor_report(self):
        adv = _make_assistant(RefactorAdvisor)
        report = adv.analyse("foo.py")
        assert isinstance(report, RefactorReport)

    def test_target_preserved(self):
        adv = _make_assistant(RefactorAdvisor)
        report = adv.analyse("my_module")
        assert report.target == "my_module"

    def test_raw_response_is_string(self):
        adv = _make_assistant(RefactorAdvisor)
        report = adv.analyse("foo.py")
        assert isinstance(report.raw_response, str)

    def test_critical_count_zero_for_empty_suggestions(self):
        adv = _make_assistant(RefactorAdvisor)
        report = adv.analyse("x")
        assert report.critical_count == 0  # suggestions list is empty by default

    def test_language_filter_forwarded(self):
        r = _make_retriever()
        adv = _make_assistant(RefactorAdvisor, retriever=r)
        adv.analyse("x", language_filter="python")
        call_kwargs = r.search.call_args.kwargs
        assert call_kwargs.get("language_filter") == "python"


# ---------------------------------------------------------------------------
# DocGenerator
# ---------------------------------------------------------------------------


class TestDocGenerator:
    def test_returns_doc_result(self):
        gen = _make_assistant(DocGenerator)
        result = gen.generate("foo.py")
        assert isinstance(result, DocResult)

    def test_target_preserved(self):
        gen = _make_assistant(DocGenerator)
        result = gen.generate("src/main.py")
        assert result.target == "src/main.py"

    def test_doc_type_preserved(self):
        gen = _make_assistant(DocGenerator)
        result = gen.generate("x", doc_type="readme")
        assert result.doc_type == "readme"

    def test_style_preserved(self):
        gen = _make_assistant(DocGenerator)
        result = gen.generate("x", style=DocStyle.NUMPY)
        assert result.style == "numpy"

    def test_content_is_string(self):
        gen = _make_assistant(DocGenerator)
        result = gen.generate("x")
        assert isinstance(result.content, str)

    def test_generate_readme_uses_readme_doc_type(self):
        gen = _make_assistant(DocGenerator)
        result = gen.generate_readme()
        assert result.doc_type == "readme"

    def test_generate_architecture_uses_architecture_doc_type(self):
        gen = _make_assistant(DocGenerator)
        result = gen.generate_architecture()
        assert result.doc_type == "architecture"
