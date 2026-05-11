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

        suggestions = self._parse_suggestions(raw_response)

        return RefactorReport(
            target=target,
            raw_response=raw_response,
            suggestions=suggestions,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _parse_suggestions(self, response: str) -> list[RefactorSuggestion]:
        """
        Parse LLM response into structured RefactorSuggestion objects.

        Expects the LLM to format suggestions as a numbered list grouped
        by severity, with each suggestion containing severity, location,
        problem, and suggested fix information.

        Parameters
        ----------
        response:
            Raw LLM response text.

        Returns
        -------
        List of parsed RefactorSuggestion objects (may be empty if
        parsing fails or LLM format is unexpected).
        """
        suggestions: list[RefactorSuggestion] = []

        lines = response.split("\n")
        current_severity = None
        current_location = None
        current_problem_lines: list[str] = []
        current_suggestion_lines: list[str] = []
        in_problem = False
        in_suggestion = False

        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Check for severity headers
            if any(sev in stripped.lower() for sev in ["critical", "major", "minor", "style"]):
                # Extract severity from the line
                for sev in ["critical", "major", "minor", "style"]:
                    if sev in stripped.lower():
                        current_severity = sev
                        break

            # Check for location marker
            elif stripped.lower().startswith("location:"):
                if current_location and current_problem_lines:
                    # Save previous suggestion before starting new one
                    if current_severity:
                        suggestions.append(
                            RefactorSuggestion(
                                severity=current_severity,
                                location=current_location,
                                problem=" ".join(current_problem_lines),
                                suggestion=" ".join(current_suggestion_lines),
                            )
                        )
                current_location = stripped[len("location:"):].strip()
                current_problem_lines = []
                current_suggestion_lines = []
                in_problem = True
                in_suggestion = False

            # Check for problem/issue marker
            elif stripped.lower().startswith("problem:"):
                in_problem = True
                in_suggestion = False
                problem_text = stripped[len("problem:"):].strip()
                if problem_text:
                    current_problem_lines.append(problem_text)

            # Check for suggestion marker
            elif stripped.lower().startswith("suggestion:") or stripped.lower().startswith("suggested fix:"):
                in_suggestion = True
                in_problem = False
                suggestion_text = (
                    stripped[len("suggestion:"):].strip()
                    if stripped.lower().startswith("suggestion:")
                    else stripped[len("suggested fix:"):].strip()
                )
                if suggestion_text:
                    current_suggestion_lines.append(suggestion_text)

            # Continue accumulating lines
            else:
                if in_problem:
                    current_problem_lines.append(stripped)
                elif in_suggestion:
                    current_suggestion_lines.append(stripped)

        # Don't forget the last suggestion
        if current_severity and current_location and current_problem_lines:
            suggestions.append(
                RefactorSuggestion(
                    severity=current_severity,
                    location=current_location,
                    problem=" ".join(current_problem_lines),
                    suggestion=" ".join(current_suggestion_lines),
                )
            )

        logger.debug(
            "Parsed %d refactor suggestions from LLM response",
            len(suggestions),
        )
        return suggestions
