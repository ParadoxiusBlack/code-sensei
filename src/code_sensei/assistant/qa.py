"""
assistant/qa.py
---------------
Code Q&A — answers natural-language questions about the indexed codebase.

Typical queries
~~~~~~~~~~~~~~~
* "What does the ``FileLoader`` class do?"
* "Where is ``embed_query`` called?"
* "How does the chunking pipeline work?"

The ``CodeQA`` assistant retrieves relevant code chunks and feeds them to
the LLM as context, following a RAG pattern.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from time import perf_counter

from ..retrieval.retriever import RetrievalResult, Retriever
from ._base import _BaseAssistant

try:
    from config.settings import RETRIEVAL_ONLY_MODE
except ImportError:
    RETRIEVAL_ONLY_MODE = False

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are CodeSensei, an expert programming assistant with deep knowledge of the \
user's codebase. Use the provided code context to answer the user's question \
accurately and concisely. If the answer cannot be determined from the context, \
say so clearly.

Rules:
- Do not invent functions, files, or behavior not present in context.
- Cite relevant file paths for concrete claims.
- Prefer a short direct answer first, then key supporting details.
- If context is insufficient, say exactly what is missing.
"""

_QA_PROMPT_TEMPLATE = """\
## Codebase context

{context}

---

## Question

{question}

## Answer
"""


@dataclass
class QAResponse:
    """Structured response from ``CodeQA``."""

    question: str
    answer: str
    sources: list[str] = field(default_factory=list)
    retrieval_results: list[RetrievalResult] = field(default_factory=list)


@dataclass
class QAQueryMetrics:
    """Per-query metrics for observability and evaluation."""

    question: str
    use_llm: bool
    retrieval_ms: float
    generation_ms: float
    total_ms: float
    result_count: int
    source_count: int


class CodeQA(_BaseAssistant):
    """
    Answers questions about the indexed codebase using RAG.

    Parameters
    ----------
    retriever:
        A configured ``Retriever`` instance.
    top_k:
        Number of chunks to retrieve per query.
    """

    def __init__(
        self,
        retriever: Retriever,
        top_k: int = 8,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.retriever = retriever
        self.top_k = top_k
        self.last_query_metrics: QAQueryMetrics | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask_stream(
        self,
        question: str,
        language_filter: str | None = None,
        path_prefix: str | None = None,
        use_llm: bool = True,
    ) -> tuple[Iterator[str], list[str], list[RetrievalResult]]:
        """Return a stream iterator plus source metadata for progressive output."""
        logger.info("CodeQA.ask_stream: %s", question[:80])

        retrieval_started = perf_counter()
        results = self.retriever.search(
            query=question,
            top_k=self.top_k,
            language_filter=language_filter,
            path_prefix=path_prefix,
        )
        retrieval_ms = (perf_counter() - retrieval_started) * 1000.0

        sources = sorted({r.source_path for r in results})

        if not use_llm or RETRIEVAL_ONLY_MODE:
            context = self._format_context(results)

            def _single() -> Iterator[str]:
                yield context

            self.last_query_metrics = QAQueryMetrics(
                question=question,
                use_llm=False,
                retrieval_ms=retrieval_ms,
                generation_ms=0.0,
                total_ms=retrieval_ms,
                result_count=len(results),
                source_count=len(sources),
            )
            return _single(), sources, results

        context = self._format_context(results)
        prompt = _QA_PROMPT_TEMPLATE.format(context=context, question=question)
        full_prompt = self._compose_prompt(_SYSTEM_PROMPT, prompt)

        generation_started = perf_counter()

        def _tracked_stream() -> Iterator[str]:
            parts: list[str] = []
            for piece in self._invoke_stream(full_prompt):
                parts.append(piece)
                yield piece

            total_ms = retrieval_ms + ((perf_counter() - generation_started) * 1000.0)
            self.last_query_metrics = QAQueryMetrics(
                question=question,
                use_llm=True,
                retrieval_ms=retrieval_ms,
                generation_ms=max(0.0, total_ms - retrieval_ms),
                total_ms=total_ms,
                result_count=len(results),
                source_count=len(sources),
            )

        return _tracked_stream(), sources, results

    def ask(
        self,
        question: str,
        language_filter: str | None = None,
        path_prefix: str | None = None,
        use_llm: bool = True,
    ) -> QAResponse:
        """
        Answer a natural-language question about the codebase.

        Parameters
        ----------
        question:
            The user's question.
        language_filter:
            Restrict retrieval to a specific language.
        path_prefix:
            Restrict retrieval to files under this path prefix.
        use_llm:
            If False, return raw retrieval results without LLM summary.

        Returns
        -------
        QAResponse
        """
        started = perf_counter()
        stream, sources, results = self.ask_stream(
            question=question,
            language_filter=language_filter,
            path_prefix=path_prefix,
            use_llm=use_llm,
        )
        answer = "".join(stream)
        retrieval_ms = 0.0
        maybe_metrics = getattr(self.retriever, "last_metrics", None)
        maybe_total_ms = (
            getattr(maybe_metrics, "total_ms", None) if maybe_metrics is not None else None
        )
        if isinstance(maybe_total_ms, (int, float)):
            retrieval_ms = float(maybe_total_ms)
        total_ms = (perf_counter() - started) * 1000.0
        generation_ms = max(0.0, total_ms - retrieval_ms)
        self.last_query_metrics = QAQueryMetrics(
            question=question,
            use_llm=use_llm,
            retrieval_ms=retrieval_ms,
            generation_ms=generation_ms,
            total_ms=total_ms,
            result_count=len(results),
            source_count=len(sources),
        )
        return QAResponse(
            question=question,
            answer=answer,
            sources=sources,
            retrieval_results=results,
        )
