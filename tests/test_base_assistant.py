from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from code_sensei.assistant._base import _BaseAssistant
from code_sensei.retrieval.retriever import RetrievalResult


class _DummyAssistant(_BaseAssistant):
    pass


def _make_assistant_with_llm(mock_llm):
    with patch.object(_DummyAssistant, "_build_llm", return_value=mock_llm):
        return _DummyAssistant()


def test_invoke_handles_plain_string_response():
    mock_llm = SimpleNamespace(invoke=lambda _messages: "plain response")
    assistant = _make_assistant_with_llm(mock_llm)

    result = assistant._invoke("hello")

    assert result == "plain response"


def test_invoke_handles_message_like_response():
    mock_llm = SimpleNamespace(invoke=lambda _messages: SimpleNamespace(content="message response"))
    assistant = _make_assistant_with_llm(mock_llm)

    result = assistant._invoke("hello")

    assert result == "message response"


def test_invoke_stream_yields_string_chunks():
    mock_llm = SimpleNamespace(stream=lambda _messages: iter(["a", "b", "c"]))
    assistant = _make_assistant_with_llm(mock_llm)

    result = "".join(assistant._invoke_stream("hello"))

    assert result == "abc"


def test_invoke_stream_yields_message_chunks():
    mock_llm = SimpleNamespace(
        stream=lambda _messages: iter([
            SimpleNamespace(content="a"),
            SimpleNamespace(content="b"),
        ])
    )
    assistant = _make_assistant_with_llm(mock_llm)

    result = "".join(assistant._invoke_stream("hello"))

    assert result == "ab"


def test_invoke_stream_falls_back_to_invoke_when_stream_unavailable():
    mock_llm = SimpleNamespace(invoke=lambda _messages: "full answer")
    assistant = _make_assistant_with_llm(mock_llm)

    result = "".join(assistant._invoke_stream("hello"))

    assert result == "full answer"


def test_format_context_returns_message_when_empty():
    assistant = _make_assistant_with_llm(SimpleNamespace(invoke=lambda _messages: "ok"))

    context = assistant._format_context([])

    assert "No relevant indexed context" in context


def test_format_context_limits_chunks_per_file_and_dedupes():
    assistant = _make_assistant_with_llm(SimpleNamespace(invoke=lambda _messages: "ok"))
    results = [
        RetrievalResult(
            chunk_id="1",
            source_path="a.py",
            language="python",
            content="same content",
            score=0.95,
        ),
        RetrievalResult(
            chunk_id="2",
            source_path="a.py",
            language="python",
            content="same content",
            score=0.90,
        ),
        RetrievalResult(
            chunk_id="3",
            source_path="a.py",
            language="python",
            content="other content",
            score=0.85,
        ),
    ]

    context = assistant._format_context(results, max_chunks_per_file=1, max_chars=10000)

    assert context.count("# File: a.py") == 1


def test_format_context_truncates_long_chunk_content():
    assistant = _make_assistant_with_llm(SimpleNamespace(invoke=lambda _messages: "ok"))
    long_content = "x" * 200
    results = [
        RetrievalResult(
            chunk_id="1",
            source_path="b.py",
            language="python",
            content=long_content,
            score=0.99,
        )
    ]

    context = assistant._format_context(results, max_chars_per_chunk=20, max_chars=10000)

    assert "...truncated" in context


def test_compose_prompt_normalizes_whitespace():
    combined = _BaseAssistant._compose_prompt("  system  ", "\nuser\n")

    assert combined == "system\n\nuser"
