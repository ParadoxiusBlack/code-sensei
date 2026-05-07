"""
assistant/_base.py
------------------
Shared base class for all assistant features.

Every assistant feature:
* receives retrieved context chunks from the ``Retriever``,
* formats them into a prompt,
* calls the LLM,
* returns a structured response.

The ``_BaseAssistant`` provides the LLM client, a helper to build a
context string from ``RetrievalResult`` objects, and sensible defaults.
"""

from __future__ import annotations

import logging
from typing import Sequence

from ..retrieval.retriever import RetrievalResult

try:
    from config.settings import CHAT_MODEL, MAX_TOKENS, TEMPERATURE
except ImportError:
    CHAT_MODEL = "gpt-4o"
    TEMPERATURE = 0.2
    MAX_TOKENS = 2048

logger = logging.getLogger(__name__)


class _BaseAssistant:
    """
    Abstract base providing LLM access and context-building utilities.

    Parameters
    ----------
    model:
        Chat model name.
    temperature:
        Sampling temperature.
    max_tokens:
        Maximum tokens in the LLM response.
    """

    def __init__(
        self,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.model = model or CHAT_MODEL
        self.temperature = temperature if temperature is not None else TEMPERATURE
        self.max_tokens = max_tokens if max_tokens is not None else MAX_TOKENS
        self._llm = self._build_llm()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_llm(self):  # type: ignore[return]
        """Build a LangChain ChatOpenAI instance (falls back to None)."""
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as exc:
            logger.warning(
                "Could not initialise LLM (%s). "
                "Assistant will return placeholder responses until a valid API key is set. "
                "Error: %s",
                self.model,
                exc,
            )
            return None

    def _format_context(
        self,
        results: Sequence[RetrievalResult],
        max_chars: int = 8000,
    ) -> str:
        """Build a context string from retrieval results, respecting a char budget."""
        parts: list[str] = []
        used = 0
        for r in results:
            header = f"# File: {r.source_path} (lang: {r.language}, score: {r.score:.2f})\n"
            block = f"{header}```{r.language}\n{r.content}\n```\n"
            if used + len(block) > max_chars:
                break
            parts.append(block)
            used += len(block)
        return "\n".join(parts)

    def _invoke(self, prompt: str) -> str:
        """Call the LLM and return the text response."""
        if self._llm is None:
            return (
                "[LLM not available — set a valid API key in .env to get real responses.]\n"
                f"Prompt received:\n{prompt[:200]}..."
            )
        try:
            from langchain_core.messages import HumanMessage

            response = self._llm.invoke([HumanMessage(content=prompt)])
            return response.content  # type: ignore[return-value]
        except Exception as exc:
            logger.error("LLM invocation failed: %s", exc)
            return f"[LLM error: {exc}]"
