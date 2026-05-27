"""
memory/conversation.py
----------------------
Multi-turn conversation memory for the CodeSensei assistant.

Design notes
~~~~~~~~~~~~
* Stores the full message history in memory (list of ``Message`` objects).
* Persists history to the SQLite cache via ``SqliteCache`` so sessions
  survive process restarts.
* Applies a sliding-window strategy when the history exceeds
  ``max_tokens``: the oldest non-system messages are dropped first.
* Exposes a LangChain ``BaseChatMessageHistory``-compatible interface so
  it can be dropped into any LangChain chain that expects a memory object.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

Role = Literal["system", "user", "assistant"]

_DEFAULT_SYSTEM_MESSAGE = (
    "You are CodeSensei, an AI assistant that helps developers understand, "
    "test, refactor, and document their codebase. "
    "You have access to an indexed vector store of the user's source code. "
    "Refer to previous messages in the conversation when relevant."
)


@dataclass
class Message:
    """A single message in the conversation history."""

    role: Role
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Message:
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", 0.0),
        )


class ConversationMemory:
    """
    Manages multi-turn conversation history for the CodeSensei assistant.

    Parameters
    ----------
    session_id:
        Unique identifier for this conversation session.  Used as the
        key when persisting to SQLite.
    system_message:
        Initial system prompt injected at the start of every conversation.
    max_messages:
        Maximum number of messages to retain (sliding window).
        The system message is never dropped.
    cache:
        Optional ``SqliteCache`` instance for persistence.  If ``None``,
        history is stored in memory only.
    """

    def __init__(
        self,
        session_id: str = "default",
        system_message: str = _DEFAULT_SYSTEM_MESSAGE,
        max_messages: int = 50,
        cache=None,  # SqliteCache | None
    ) -> None:
        self.session_id = session_id
        self.max_messages = max_messages
        self._cache = cache
        self._messages: list[Message] = [Message(role="system", content=system_message)]
        self._load_from_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_user_message(self, content: str) -> None:
        """Append a user message to the history."""
        self._append(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        """Append an assistant reply to the history."""
        self._append(Message(role="assistant", content=content))

    def get_messages(self) -> list[Message]:
        """Return a copy of the current message history."""
        return list(self._messages)

    def get_messages_for_llm(self) -> list[dict]:
        """Return messages formatted as ``{"role": ..., "content": ...}`` dicts."""
        return [{"role": m.role, "content": m.content} for m in self._messages]

    def clear(self) -> None:
        """Clear all messages except the system message."""
        system = self._messages[0]
        self._messages = [system]
        self._save_to_cache()
        logger.debug("Conversation memory cleared for session '%s'.", self.session_id)

    @property
    def message_count(self) -> int:
        """Number of messages (including the system message)."""
        return len(self._messages)

    @property
    def last_user_message(self) -> str | None:
        """Return the content of the most recent user message, or ``None``."""
        for msg in reversed(self._messages):
            if msg.role == "user":
                return msg.content
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _append(self, message: Message) -> None:
        self._messages.append(message)
        self._trim()
        self._save_to_cache()

    def _trim(self) -> None:
        """Remove oldest non-system messages when over the limit."""
        while len(self._messages) > self.max_messages + 1:  # +1 for system msg
            # Remove the second message (index 1) to keep system at index 0.
            if len(self._messages) > 1:
                self._messages.pop(1)
            else:
                break

    def _save_to_cache(self) -> None:
        if self._cache is None:
            return
        try:
            data = json.dumps([m.to_dict() for m in self._messages])
            self._cache.set(f"conversation:{self.session_id}", data)
        except Exception as exc:
            logger.warning("Failed to persist conversation: %s", exc)

    def _load_from_cache(self) -> None:
        if self._cache is None:
            return
        try:
            data = self._cache.get(f"conversation:{self.session_id}")
            if data:
                loaded = [Message.from_dict(d) for d in json.loads(data)]
                if loaded:
                    self._messages = loaded
                    logger.debug(
                        "Loaded %d messages for session '%s'.",
                        len(loaded),
                        self.session_id,
                    )
        except Exception as exc:
            logger.warning("Failed to load conversation from cache: %s", exc)
