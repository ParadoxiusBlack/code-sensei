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
    from config.settings import (
        CHAT_MODEL,
        MAX_TOKENS,
        TEMPERATURE,
        HYBRID_LLM_MODE,
        OLLAMA_BASE_URL,
        OLLAMA_MODEL,
        OPENAI_API_KEY,
    )
except ImportError:
    CHAT_MODEL = "gpt-4o"
    TEMPERATURE = 0.2
    MAX_TOKENS = 2048
    HYBRID_LLM_MODE = True
    OLLAMA_BASE_URL = "http://localhost:11434"
    OLLAMA_MODEL = "mistral"
    OPENAI_API_KEY = ""

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
        """Build LLM with hybrid fallback: Ollama → OpenAI → None."""
        if HYBRID_LLM_MODE:
            # Try Ollama first (local, no API key needed)
            llm = self._try_ollama()
            if llm:
                logger.info("Using local Ollama LLM (%s)", OLLAMA_MODEL)
                return llm
            
            # Fall back to OpenAI
            if OPENAI_API_KEY:
                llm = self._try_openai()
                if llm:
                    logger.info("Using OpenAI LLM (%s)", self.model)
                    return llm
            
            # No LLM available
            logger.warning(
                "No LLM available: Ollama not running and no OpenAI API key. "
                "Using retrieval-only mode (showing raw code chunks)."
            )
            return None
        else:
            # Original behavior: OpenAI only
            try:
                from langchain_openai import ChatOpenAI

                return ChatOpenAI(
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            except Exception as exc:
                logger.warning(
                    "Could not initialise OpenAI LLM (%s). "
                    "Assistant will return placeholder responses. "
                    "Error: %s",
                    self.model,
                    exc,
                )
                return None

    def _try_ollama(self):  # type: ignore[return]
        """Attempt to connect to local Ollama instance."""
        try:
            from langchain_ollama import OllamaLLM

            llm = OllamaLLM(
                model=OLLAMA_MODEL,
                base_url=OLLAMA_BASE_URL,
                temperature=self.temperature,
            )
            # Test connection with a simple call
            llm.invoke("test")
            return llm
        except Exception as exc:
            logger.debug("Ollama not available: %s", exc)
            return None

    def _try_openai(self):  # type: ignore[return]
        """Attempt to connect to OpenAI API."""
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as exc:
            logger.debug("OpenAI not available: %s", exc)
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

            # Chat models usually return message objects with `.content`,
            # while some local LLM wrappers can return plain strings.
            if isinstance(response, str):
                return response

            content = getattr(response, "content", None)
            if isinstance(content, str):
                return content

            return str(response)
        except Exception as exc:
            logger.error("LLM invocation failed: %s", exc)
            return f"[LLM error: {exc}]"
