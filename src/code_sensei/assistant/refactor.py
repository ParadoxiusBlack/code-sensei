"""
assistant/refactor.py
---------------------
Refactor-suggestion assistant.

Analyses retrieved code chunks for:
* Code smells (long methods, duplicated logic, magic numbers, …)
* Design-pattern opportunities
* Performance anti-patterns
* Naming and readability issues

Returns a structured ``RefactorReport`` with actionable suggestions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..retrieval.retriever import Retriever
from ._base import _BaseAssistant

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are CodeSensei, a senior software architect and code-quality expert. \
Your job is to review code and provide actionable, prioritised refactoring \
suggestions. Be specific: name the file, function, or line range, explain \
the problem, and propose a concrete improvement. Group suggestions by \
severity (critical > major > minor > style).
"""

_REFACTOR_TEMPLATE = """\
## Code under review

{context}

---

## Refactoring analysis

Analyse the code above for the following categories:
1. Code smells (long methods, god classes, duplicated logic, magic numbers)
2. SOLID / design-principle violations
3. Performance anti-patterns
4. Error-handling gaps
5. Naming and readability issues

For each issue found:
- Severity: critical | major | minor | style
- Location: file path + function/class name
- Problem description (1–2 sentences)
- Suggested fix (concrete code snippet or description)

Format your response as a numbered list grouped by severity.
"""


@dataclass
class RefactorSuggestion:
    """A single refactoring recommendation."""

    severity: str  # critical | major | minor | style
    location: str
    problem: str
    suggestion: str


@dataclass
class RefactorReport:
    """Aggregated refactoring report for a target path or query."""

    target: str
    raw_response: str
    suggestions: list[RefactorSuggestion] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for s in self.suggestions if s.severity == "critical")

    @property
    def major_count(self) -> int:
        return sum(1 for s in self.suggestions if s.severity == "major")


class RefactorAdvisor(_BaseAssistant):
    """
    Identifies code smells and proposes refactoring improvements.

    Parameters
    ----------
    retriever:
        A configured ``Retriever`` instance.
    top_k:
        Number of context chunks to retrieve.
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyse(
        self,
        target: str,
        language_filter: str | None = None,
    ) -> RefactorReport:
        """
        Retrieve code for ``target`` and return refactoring suggestions.

        Parameters
        ----------
        target:
            File path, module name, or natural-language query
            (e.g. ``"authentication module"``).
        language_filter:
            Restrict retrieval to a specific language.

        Returns
        -------
        RefactorReport
        """
        logger.info("RefactorAdvisor.analyse: %s", target)

        results = self.retriever.search(
            query=target,
            top_k=self.top_k,
            language_filter=language_filter,
        )

        context = self._format_context(results)
        prompt = _REFACTOR_TEMPLATE.format(context=context)
        raw_response = self._invoke(_SYSTEM_PROMPT + "\n\n" + prompt)

        return RefactorReport(
            target=target,
            raw_response=raw_response,
        )
