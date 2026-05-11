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
