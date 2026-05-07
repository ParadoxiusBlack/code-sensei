"""
assistant/doc_generator.py
--------------------------
Documentation generation assistant.

Produces:
* Module / class / function docstrings
* README drafts
* Architecture overview (textual)
* API reference summaries

Output is plain text / Markdown that the caller can write to a file or
display in the CLI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from ..retrieval.retriever import Retriever
from ._base import _BaseAssistant

logger = logging.getLogger(__name__)


class DocStyle(str, Enum):
    """Supported documentation styles."""

    GOOGLE = "google"
    NUMPY = "numpy"
    SPHINX = "sphinx"
    MARKDOWN = "markdown"


_SYSTEM_PROMPT = """\
You are CodeSensei, a technical writer and senior software engineer. \
Your job is to produce clear, accurate, and complete documentation for \
the provided code. Follow the requested documentation style precisely. \
Do not invent behaviour that is not present in the code.
"""

_DOC_TEMPLATE = """\
## Code to document

{context}

---

## Documentation task

Generate {doc_type} for the code above.

Style: {style}
{extra_instructions}

Respond with only the documentation content (Markdown unless the style \
dictates otherwise).
"""

_DOC_TYPE_INSTRUCTIONS: dict[str, str] = {
    "docstrings": (
        "Write docstrings for every public class, method, and function. "
        "Include Parameters, Returns, Raises, and a short description."
    ),
    "readme": (
        "Write a comprehensive README.md that includes: "
        "project overview, installation, usage examples, "
        "configuration, and contributing guidelines."
    ),
    "architecture": (
        "Write a textual architecture overview that describes: "
        "high-level components, data flow, key design decisions, "
        "and extension points. Use ASCII diagrams where helpful."
    ),
    "api_reference": (
        "Generate an API reference in Markdown. "
        "For each public symbol include: signature, description, "
        "parameters with types, return value, and a usage example."
    ),
}


@dataclass
class DocResult:
    """Result of a documentation-generation request."""

    target: str
    doc_type: str
    style: str
    content: str


class DocGenerator(_BaseAssistant):
    """
    Generates documentation for code retrieved from the indexed codebase.

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
        doc_type: str = "docstrings",
        style: str | DocStyle = DocStyle.GOOGLE,
        language_filter: str | None = None,
    ) -> DocResult:
        """
        Generate documentation for a file, module, or natural-language target.

        Parameters
        ----------
        target:
            File path, module name, or natural-language query.
        doc_type:
            One of ``"docstrings"``, ``"readme"``, ``"architecture"``,
            ``"api_reference"``.
        style:
            Documentation style (``DocStyle`` enum or string).
        language_filter:
            Restrict retrieval to a specific language.

        Returns
        -------
        DocResult
        """
        logger.info("DocGenerator.generate: %s (%s)", target, doc_type)

        results = self.retriever.search(
            query=target,
            top_k=self.top_k,
            language_filter=language_filter,
        )

        context = self._format_context(results)
        extra = _DOC_TYPE_INSTRUCTIONS.get(
            doc_type,
            f"Generate {doc_type} documentation.",
        )
        style_str = style.value if isinstance(style, DocStyle) else str(style)

        prompt = _DOC_TEMPLATE.format(
            context=context,
            doc_type=doc_type,
            style=style_str,
            extra_instructions=extra,
        )

        content = self._invoke(_SYSTEM_PROMPT + "\n\n" + prompt)

        return DocResult(
            target=target,
            doc_type=doc_type,
            style=style_str,
            content=content,
        )

    def generate_readme(self, path_prefix: str = "") -> DocResult:
        """Convenience wrapper that generates a project README."""
        return self.generate(
            target=path_prefix or "entire project",
            doc_type="readme",
            style=DocStyle.MARKDOWN,
        )

    def generate_architecture(self, path_prefix: str = "") -> DocResult:
        """Convenience wrapper that generates an architecture overview."""
        return self.generate(
            target=path_prefix or "system architecture",
            doc_type="architecture",
            style=DocStyle.MARKDOWN,
        )
