"""
usage_tracker.py
----------------
Tracks LLM token usage and GitHub Copilot premium request consumption.

Data is persisted in ``~/.code_sensei/usage.json`` so statistics survive
across sessions and projects.

GitHub Copilot billing model (as of 2025)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* **Included models** (gpt-4o, gpt-4o-mini): unlimited requests, no premium
  budget consumed.
* **Premium models** (claude-*, o1, o3-mini, gemini-2.0-flash, …): each
  request counts against the plan's monthly premium-request allowance
  (Individual: 300/month, Business: configurable).

Since the Copilot API does not expose remaining balance, this tracker counts
requests locally.  A module-level singleton is exposed via ``get_tracker()``.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Premium-model registry
# ---------------------------------------------------------------------------

#: Models that consume GitHub Copilot premium requests (June 2025).
COPILOT_PREMIUM_MODELS: frozenset[str] = frozenset(
    {
        "claude-3.5-sonnet",
        "claude-3.7-sonnet",
        "claude-3-5-sonnet-20241022",
        "claude-3-7-sonnet-20250219",
        "o1",
        "o1-mini",
        "o3-mini",
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
    }
)

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

_USAGE_FILE = Path.home() / ".code_sensei" / "usage.json"

_singleton_lock = threading.Lock()
_singleton: UsageTracker | None = None


class UsageTracker:
    """
    File-backed cumulative LLM usage tracker.

    Thread-safe; all mutations hold ``self._lock`` before writing to disk.
    """

    def __init__(self, usage_file: Path | None = None) -> None:
        self._path = Path(usage_file or _USAGE_FILE).resolve()
        self._lock = threading.Lock()
        self._data: dict[str, Any] = self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        try:
            if self._path.exists():
                return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not load usage file %s: %s", self._path, exc)
        return {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not save usage file %s: %s", self._path, exc)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record a completed LLM request's token counts."""
        with self._lock:
            p = self._data.setdefault(provider, {})
            m = p.setdefault(model, {"input_tokens": 0, "output_tokens": 0, "requests": 0})
            m["input_tokens"] += input_tokens
            m["output_tokens"] += output_tokens
            m["requests"] += 1
            self._save()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_stats(self, provider: str, model: str) -> dict[str, int]:
        """Return cumulative stats for a specific provider/model pair."""
        defaults: dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "requests": 0}
        return {**defaults, **self._data.get(provider, {}).get(model, {})}

    def get_copilot_premium_requests(self) -> int:
        """Total premium requests used across all Copilot premium models this period."""
        total = 0
        for model, stats in self._data.get("copilot", {}).items():
            if model in COPILOT_PREMIUM_MODELS:
                total += stats.get("requests", 0)
        return total

    def get_all_copilot_requests(self) -> int:
        """Total requests made to any Copilot model (premium + included)."""
        return sum(s.get("requests", 0) for s in self._data.get("copilot", {}).values())

    # ------------------------------------------------------------------
    # Resets
    # ------------------------------------------------------------------

    def reset_copilot(self) -> None:
        """Reset Copilot usage counters (call at the start of each billing month)."""
        with self._lock:
            self._data.pop("copilot", None)
            self._save()

    def reset_all(self) -> None:
        """Reset all provider usage counters."""
        with self._lock:
            self._data.clear()
            self._save()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


def get_tracker() -> UsageTracker:
    """Return the process-wide ``UsageTracker`` singleton."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = UsageTracker()
    return _singleton
