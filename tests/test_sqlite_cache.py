"""
tests/test_sqlite_cache.py
--------------------------
Unit tests for code_sensei.cache.sqlite_cache.
"""

from __future__ import annotations

import time

import pytest
from code_sensei.cache.sqlite_cache import SqliteCache


@pytest.fixture()
def cache(tmp_path):
    db = tmp_path / "test.db"
    return SqliteCache(db_path=db)


class TestSqliteCache:
    def test_set_and_get_string(self, cache):
        cache.set("key1", "hello")
        assert cache.get("key1") == "hello"

    def test_set_and_get_dict(self, cache):
        data = {"a": 1, "b": [1, 2, 3]}
        cache.set("key2", data)
        assert cache.get("key2") == data

    def test_get_missing_key_returns_default(self, cache):
        assert cache.get("nope") is None
        assert cache.get("nope", default="fallback") == "fallback"

    def test_overwrite_existing_key(self, cache):
        cache.set("k", "old")
        cache.set("k", "new")
        assert cache.get("k") == "new"

    def test_delete_removes_key(self, cache):
        cache.set("del_me", 42)
        cache.delete("del_me")
        assert cache.get("del_me") is None

    def test_clear_removes_all_entries(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_ttl_expiry(self, cache):
        cache.set("temp", "value", ttl=0.01)  # 10 ms TTL
        time.sleep(0.05)
        assert cache.get("temp") is None

    def test_no_ttl_does_not_expire(self, cache):
        cache.set("permanent", "value")
        # Not waiting; just verify it's still there
        assert cache.get("permanent") == "value"

    def test_purge_expired_returns_count(self, cache):
        cache.set("e1", "v", ttl=0.01)
        cache.set("e2", "v", ttl=0.01)
        time.sleep(0.05)
        removed = cache.purge_expired()
        assert removed == 2

    def test_purge_expired_leaves_valid_entries(self, cache):
        cache.set("keep", "v", ttl=9999)
        cache.set("expire", "v", ttl=0.01)
        time.sleep(0.05)
        cache.purge_expired()
        assert cache.get("keep") == "v"

    def test_context_manager(self, tmp_path):
        db = tmp_path / "ctx.db"
        with SqliteCache(db_path=db) as c:
            c.set("x", 99)
            assert c.get("x") == 99

    def test_db_file_created(self, tmp_path):
        db = tmp_path / "sub" / "nested" / "cache.db"
        c = SqliteCache(db_path=db)
        c.set("k", "v")
        assert db.exists()

    def test_numeric_value(self, cache):
        cache.set("num", 3.14)
        assert cache.get("num") == pytest.approx(3.14)

    def test_list_value(self, cache):
        cache.set("lst", [1, 2, 3])
        assert cache.get("lst") == [1, 2, 3]
