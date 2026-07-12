"""Covers rag.ingest.list_runbooks()'s last-ingested-time reporting and its
fallback to the raw markdown corpus when Postgres has nothing for this user
yet (e.g. before their first ingest)."""
from datetime import datetime, timezone

import rag.ingest as ingest


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        return self

    def fetchall(self):
        return self._rows


def test_list_runbooks_reports_last_ingested_time(monkeypatch):
    when = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(ingest.psycopg, "connect", lambda *a, **kw: _FakeConn([("deploy-failures", 3, when)]))

    result = ingest.list_runbooks(owner_user_id=1)

    assert result == [{"title": "deploy-failures", "chunk_count": 3, "last_ingested_at": when.isoformat()}]


def test_list_runbooks_falls_back_to_markdown_files_when_db_unreachable(monkeypatch):
    def boom(*a, **kw):
        raise ConnectionError("db unreachable")

    monkeypatch.setattr(ingest.psycopg, "connect", boom)

    result = ingest.list_runbooks(owner_user_id=1)

    assert all(r["last_ingested_at"] is None for r in result)
    assert all(r["chunk_count"] == 0 for r in result)
