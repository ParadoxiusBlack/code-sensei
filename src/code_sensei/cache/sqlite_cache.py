"""SQLite-backed key-value cache."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any


class SqliteCache:
    """Simple SQLite-backed cache with optional per-key TTL."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            path: str | Path = os.getenv("CACHE_DB_PATH", "cache.db")
        else:
            path = db_path
        self._db_path = Path(path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at REAL
            )
            """)
        self._conn.commit()

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a value under ``key`` with optional ``ttl`` in seconds."""
        expires_at = None if ttl is None else time.time() + float(ttl)
        payload = json.dumps(value)
        self._conn.execute(
            """
            INSERT OR REPLACE INTO cache_entries (key, value, expires_at)
            VALUES (?, ?, ?)
            """,
            (key, payload, expires_at),
        )
        self._conn.commit()

    def get(self, key: str, default: Any = None) -> Any:
        """Return cached value for ``key`` or ``default`` when missing/expired."""
        row = self._conn.execute(
            "SELECT value, expires_at FROM cache_entries WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default

        payload, expires_at = row
        if expires_at is not None and float(expires_at) <= time.time():
            self.delete(key)
            return default

        return json.loads(payload)

    def delete(self, key: str) -> None:
        """Remove one cache entry."""
        self._conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
        self._conn.commit()

    def clear(self) -> None:
        """Remove all cache entries."""
        self._conn.execute("DELETE FROM cache_entries")
        self._conn.commit()

    def purge_expired(self) -> int:
        """Delete expired entries and return the number of removed rows."""
        cursor = self._conn.execute(
            "DELETE FROM cache_entries WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (time.time(),),
        )
        self._conn.commit()
        return int(cursor.rowcount)

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def __enter__(self) -> SqliteCache:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
