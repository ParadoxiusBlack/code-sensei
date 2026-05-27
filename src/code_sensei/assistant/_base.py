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
from collections.abc import Iterator, Sequence

from ..errors import ModelNotFoundError, OllamaConnectionError
from ..retrieval.retriever import RetrievalResult

try:
    from config.settings import (
        CHAT_MODEL,
        HYBRID_LLM_MODE,
        MAX_CHARS_PER_CHUNK,
        MAX_CHUNKS_PER_FILE,
        MAX_CONTEXT_CHARS,
        MAX_TOKENS,
        OLLAMA_BASE_URL,
        OLLAMA_MODEL,
        OPENAI_API_KEY,
        TEMPERATURE,
    )
except ImportError:
    CHAT_MODEL = "gpt-4o"
    TEMPERATURE = 0.2
    MAX_TOKENS = 2048
    HYBRID_LLM_MODE = True
    OLLAMA_BASE_URL = "http://localhost:11434"
    OLLAMA_MODEL = "mistral"
    OPENAI_API_KEY = ""
    MAX_CONTEXT_CHARS = 8000
    MAX_CHARS_PER_CHUNK = 1400
    MAX_CHUNKS_PER_FILE = 2

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
        #: Human-readable explanation of why the LLM is unavailable (None = OK).
        self.llm_init_error: str | None = None
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

            # No LLM available — preserve the most helpful hint for the CLI.
            if not self.llm_init_error:
                self.llm_init_error = (
                    "No LLM is available. Ollama is not running and no OpenAI API key "
                    "is configured. Run 'ollama serve' to start Ollama."
                )
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
        """Attempt to connect to local Ollama instance.

        On failure sets ``self.llm_init_error`` with an actionable message
        so the CLI can surface it to the user.
        """
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
            exc_lower = str(exc).lower()
            if (
                "connection refused" in exc_lower
                or "connect error" in exc_lower
                or "connectionerror" in exc_lower
                or "cannot connect" in exc_lower
                or "failed to connect" in exc_lower
            ):
                err = OllamaConnectionError(OLLAMA_BASE_URL)
                self.llm_init_error = f"{err}  Hint: {err.hint}"
                logger.debug("Ollama connection refused: %s", exc)
            elif "not found" in exc_lower or "404" in exc_lower:
                err = ModelNotFoundError(OLLAMA_MODEL)
                self.llm_init_error = f"{err}  Hint: {err.hint}"
                logger.debug("Ollama model not found: %s", exc)
            else:
                self.llm_init_error = f"Ollama unavailable: {exc}"
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
        max_chars: int | None = None,
        max_chars_per_chunk: int | None = None,
        max_chunks_per_file: int | None = None,
    ) -> str:
        """Build context string with budgeted, deduplicated, file-balanced chunks."""
        if not results:
            return "[No relevant indexed context found.]"

        max_chars = MAX_CONTEXT_CHARS if max_chars is None else max_chars
        max_chars_per_chunk = (
            MAX_CHARS_PER_CHUNK if max_chars_per_chunk is None else max_chars_per_chunk
        )
        max_chunks_per_file = (
            MAX_CHUNKS_PER_FILE if max_chunks_per_file is None else max_chunks_per_file
        )

        parts: list[str] = []
        used = 0
        seen_keys: set[tuple[str, str]] = set()
        per_file_counts: dict[str, int] = {}

        for r in results:
            file_count = per_file_counts.get(r.source_path, 0)
            if file_count >= max_chunks_per_file:
                continue

            # Drop near-duplicate chunks to keep prompt budget focused.
            dedupe_key = (r.source_path, r.content[:200])
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)

            content = r.content
            if len(content) > max_chars_per_chunk:
                content = content[:max_chars_per_chunk].rstrip() + "\n# ...truncated"

            header = f"# File: {r.source_path} (lang: {r.language}, score: {r.score:.2f})\n"
            block = f"{header}```{r.language}\n{content}\n```\n"
            if used + len(block) > max_chars:
                break
            parts.append(block)
            used += len(block)
            per_file_counts[r.source_path] = file_count + 1

        return "\n".join(parts)

    @staticmethod
    def _compose_prompt(system_prompt: str, user_prompt: str) -> str:
        """Compose prompts consistently with light normalization."""
        sys_clean = system_prompt.strip()
        user_clean = user_prompt.strip()
        return f"{sys_clean}\n\n{user_clean}"

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
            return self._response_to_text(response)
        except Exception as exc:
            logger.error("LLM invocation failed: %s", exc)
            return f"[LLM error: {exc}]"

    def _invoke_stream(self, prompt: str) -> Iterator[str]:
        """Stream LLM output token/chunk-by-chunk where supported."""
        if self._llm is None:
            yield (
                "[LLM not available — set a valid API key in .env to get real responses.]\n"
                f"Prompt received:\n{prompt[:200]}..."
            )
            return

        try:
            from langchain_core.messages import HumanMessage

            if hasattr(self._llm, "stream"):
                for chunk in self._llm.stream([HumanMessage(content=prompt)]):
                    text = self._response_to_text(chunk)
                    if text:
                        yield text
                return

            # Fallback for LLM wrappers that do not implement stream.
            yield self._invoke(prompt)
        except Exception as exc:
            logger.error("LLM stream invocation failed: %s", exc)
            yield f"[LLM error: {exc}]"

    @staticmethod
    def _response_to_text(response: object) -> str:
        """Normalize different LangChain response shapes to plain text."""
        if isinstance(response, str):
            return response

        content = getattr(response, "content", None)
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            if parts:
                return "".join(parts)

        text_attr = getattr(response, "text", None)
        if isinstance(text_attr, str):
            return text_attr

        return str(response)
