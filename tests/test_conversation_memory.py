"""
tests/test_conversation_memory.py
----------------------------------
Unit tests for code_sensei.memory.conversation.
"""

from __future__ import annotations

import pytest

from code_sensei.memory.conversation import ConversationMemory, Message


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------


class TestMessage:
    def test_to_dict_round_trip(self):
        msg = Message(role="user", content="hello", timestamp=1000.0)
        d = msg.to_dict()
        reconstructed = Message.from_dict(d)
        assert reconstructed.role == msg.role
        assert reconstructed.content == msg.content
        assert reconstructed.timestamp == msg.timestamp

    def test_from_dict_missing_timestamp_defaults_to_zero(self):
        msg = Message.from_dict({"role": "assistant", "content": "hi"})
        assert msg.timestamp == 0.0


# ---------------------------------------------------------------------------
# ConversationMemory (no cache)
# ---------------------------------------------------------------------------


class TestConversationMemory:
    def test_initial_state_has_system_message(self):
        mem = ConversationMemory()
        messages = mem.get_messages()
        assert messages[0].role == "system"

    def test_add_user_message(self):
        mem = ConversationMemory()
        mem.add_user_message("Hello!")
        assert any(m.role == "user" and m.content == "Hello!" for m in mem.get_messages())

    def test_add_assistant_message(self):
        mem = ConversationMemory()
        mem.add_assistant_message("Hi there!")
        assert any(
            m.role == "assistant" and m.content == "Hi there!" for m in mem.get_messages()
        )

    def test_message_count_increments(self):
        mem = ConversationMemory()
        initial = mem.message_count
        mem.add_user_message("a")
        mem.add_assistant_message("b")
        assert mem.message_count == initial + 2

    def test_clear_removes_non_system_messages(self):
        mem = ConversationMemory()
        mem.add_user_message("x")
        mem.add_assistant_message("y")
        mem.clear()
        messages = mem.get_messages()
        assert len(messages) == 1
        assert messages[0].role == "system"

    def test_last_user_message_returns_latest(self):
        mem = ConversationMemory()
        mem.add_user_message("first")
        mem.add_user_message("second")
        assert mem.last_user_message == "second"

    def test_last_user_message_none_when_empty(self):
        mem = ConversationMemory()
        assert mem.last_user_message is None

    def test_get_messages_returns_copy(self):
        mem = ConversationMemory()
        msgs = mem.get_messages()
        msgs.append(Message(role="user", content="injected"))
        assert mem.message_count == 1  # should not have grown

    def test_get_messages_for_llm_format(self):
        mem = ConversationMemory()
        mem.add_user_message("q")
        dicts = mem.get_messages_for_llm()
        for d in dicts:
            assert "role" in d
            assert "content" in d

    def test_sliding_window_trims_oldest_non_system(self):
        mem = ConversationMemory(max_messages=3)
        for i in range(10):
            mem.add_user_message(f"msg {i}")
        # System message is always kept; at most max_messages+1 total
        assert mem.message_count <= 4  # 1 system + 3 user
        # System message is still first
        assert mem.get_messages()[0].role == "system"

    def test_custom_system_message(self):
        mem = ConversationMemory(system_message="You are a Python tutor.")
        assert mem.get_messages()[0].content == "You are a Python tutor."


# ---------------------------------------------------------------------------
# ConversationMemory with mock cache
# ---------------------------------------------------------------------------


class TestConversationMemoryWithCache:
    def test_saves_to_cache_on_add(self):
        from unittest.mock import MagicMock

        cache = MagicMock()
        cache.get.return_value = None
        mem = ConversationMemory(session_id="test-session", cache=cache)
        mem.add_user_message("hello")
        cache.set.assert_called()

    def test_loads_from_cache_on_init(self):
        import json
        from unittest.mock import MagicMock

        stored = [
            {"role": "system", "content": "You are helpful.", "timestamp": 1.0},
            {"role": "user", "content": "cached question", "timestamp": 2.0},
        ]
        cache = MagicMock()
        cache.get.return_value = json.dumps(stored)
        mem = ConversationMemory(session_id="sess", cache=cache)
        assert any(m.content == "cached question" for m in mem.get_messages())
