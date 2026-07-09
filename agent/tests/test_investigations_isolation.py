"""Proves investigations.py's per-user isolation against an in-memory
stand-in for Postgres -- exercises the real start/get_by_id/list_recent SQL-
building logic (not a mocked-away function), since a missing owner_user_id
filter here would let one user read another's investigation history."""
import pytest

import investigations as store


class _FakeConn:
    def __init__(self, table):
        self.table = table  # id -> row dict
        self._next_id = max(table, default=0) + 1
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        sql = " ".join(sql.split())
        params = params or ()

        if sql.startswith("INSERT INTO investigations"):
            source, source_ref, alert_text, deployment_id, owner_user_id = params
            row_id = self._next_id
            self._next_id += 1
            self.table[row_id] = {
                "id": row_id, "source": source, "source_ref": source_ref, "alert_text": alert_text,
                "status": "running", "result": None, "reviewed": False,
                "created_at": "2026-01-01T00:00:00Z", "finished_at": None,
                "deployment_id": deployment_id, "owner_user_id": owner_user_id,
                "pending_action": None, "feedback_rating": None, "feedback_notes": None,
            }
            self._result = (row_id,)
        elif sql.startswith("SELECT") and "FROM investigations WHERE id = %s AND owner_user_id = %s" in sql:
            investigation_id, owner_user_id = params
            row = self.table.get(investigation_id)
            self._result = (
                tuple(row[c] for c in store._COLUMNS)
                if row and row["owner_user_id"] == owner_user_id
                else None
            )
        elif sql.startswith("SELECT") and sql.startswith("SELECT {} FROM investigations".format(", ".join(store._COLUMNS))):
            owner_user_id = params[0]
            rows = [r for r in self.table.values() if r["owner_user_id"] == owner_user_id]
            self._rows = [tuple(r[c] for c in store._COLUMNS) for r in rows]
        else:
            raise AssertionError(f"unexpected SQL in fake connection: {sql!r}")
        return self

    def fetchone(self):
        return self._result

    def fetchall(self):
        return getattr(self, "_rows", [])


@pytest.fixture
def fake_db(monkeypatch):
    table = {}
    monkeypatch.setattr(store, "_connect", lambda: _FakeConn(table))
    return table


def test_get_by_id_returns_none_for_a_different_owner(fake_db):
    investigation_id = store.start("manual", None, "checkout down", 1)
    assert store.get_by_id(investigation_id, 1) is not None
    assert store.get_by_id(investigation_id, 2) is None


def test_list_recent_only_shows_the_calling_users_own_investigations(fake_db):
    store.start("manual", None, "user 1's incident", 1)
    store.start("manual", None, "user 2's incident", 2)

    user_1_investigations = store.list_recent(1)
    user_2_investigations = store.list_recent(2)

    assert [i["alert_text"] for i in user_1_investigations] == ["user 1's incident"]
    assert [i["alert_text"] for i in user_2_investigations] == ["user 2's incident"]
