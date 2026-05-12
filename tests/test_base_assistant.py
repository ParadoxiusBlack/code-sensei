from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from code_sensei.assistant._base import _BaseAssistant


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
