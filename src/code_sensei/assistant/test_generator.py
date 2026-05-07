"""
assistant/test_generator.py
---------------------------
Automated test generation for source files.

The ``TestGenerator`` retrieves context for a given file or function,
then asks the LLM to produce:
* Unit tests (pytest / jest / junit style)
* Integration test skeletons
* Mock / stub suggestions

Output is returned as a string containing test code, which the caller
can write to a file or display in the CLI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..retrieval.retriever import Retriever
from ._base import _BaseAssistant

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are CodeSensei, an expert software engineer specialising in test-driven \
development. Your job is to write high-quality, idiomatic tests for the \
code shown. Follow best practices: arrange-act-assert, descriptive test names, \
edge-case coverage, and proper mocking of external dependencies.
"""

_TEST_GEN_TEMPLATE = """\
## Source code to test

{context}

---

## Task

Generate comprehensive tests for the code above.

Requirements:
- Framework: {framework}
- Test types: {test_types}
- Language: {language}

Include:
1. Unit tests for every public function / method.
2. Edge cases (empty input, None, boundary values).
3. Mock / patch declarations where external I/O is involved.
4. Brief inline comments explaining what each test validates.

Respond with only the test code, no explanations outside of code comments.
"""


@dataclass
class TestGenerationResult:
    """Result of a test-generation request."""

    source_path: str
    test_code: str
    framework: str
    language: str


class TestGenerator(_BaseAssistant):
    """
    Generates unit and integration tests for a given source file or function.

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
        top_k: int = 6,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.retriever = retriever
        self.top_k = top_k

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        target: str,
        framework: str = "pytest",
        test_types: str = "unit, integration",
        language: str | None = None,
    ) -> TestGenerationResult:
        """
        Generate tests for a file path or function/class name.

        Parameters
        ----------
        target:
            File path or symbol name to generate tests for.
        framework:
            Test framework (e.g. ``"pytest"``, ``"jest"``, ``"junit"``).
        test_types:
            Comma-separated list of test types (e.g. ``"unit, integration"``).
        language:
            Language filter for retrieval (inferred from path if not set).

        Returns
        -------
        TestGenerationResult
        """
        logger.info("TestGenerator.generate: %s (%s)", target, framework)

        results = self.retriever.search(
            query=f"implementation of {target}",
            top_k=self.top_k,
            path_prefix=target if "/" in target or "\\" in target else None,
        )

        inferred_language = language or (
            results[0].language if results else "python"
        )
        context = self._format_context(results)

        prompt = _TEST_GEN_TEMPLATE.format(
            context=context,
            framework=framework,
            test_types=test_types,
            language=inferred_language,
        )

        test_code = self._invoke(_SYSTEM_PROMPT + "\n\n" + prompt)

        return TestGenerationResult(
            source_path=target,
            test_code=test_code,
            framework=framework,
            language=inferred_language,
        )
