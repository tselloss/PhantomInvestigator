"""Proves clients.py's per-user isolation with an in-memory stand-in for
Postgres (not a fully mocked-away function) -- these exercise the real
get_client/list_clients/create_client SQL-building logic, not just that a
mock was called with the right arguments, since a missing owner_user_id
filter here is exactly the kind of silent cross-tenant leak this whole pass
exists to prevent."""
import pytest

import clients as store


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

        if sql.startswith("INSERT INTO clients"):
            owner_user_id, name, slug, notes = params
            row_id = self._next_id
            self._next_id += 1
            row = {
                "id": row_id, "owner_user_id": owner_user_id, "name": name,
                "slug": slug, "notes": notes, "created_at": "2026-01-01T00:00:00Z", "archived_at": None,
            }
            self.table[row_id] = row
            self._result = tuple(row[c] for c in store._CLIENT_COLUMNS)
        elif sql.startswith("SELECT") and "FROM clients WHERE id = %s AND owner_user_id = %s" in sql:
            client_id, owner_user_id = params
            row = self.table.get(client_id)
            self._result = (
                tuple(row[c] for c in store._CLIENT_COLUMNS)
                if row and row["owner_user_id"] == owner_user_id
                else None
            )
        elif sql.startswith("SELECT") and "FROM clients WHERE owner_user_id = %s" in sql:
            (owner_user_id,) = params
            rows = [r for r in self.table.values() if r["owner_user_id"] == owner_user_id]
            self._rows = [tuple(r[c] for c in store._CLIENT_COLUMNS) for r in rows]
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


def test_get_client_returns_none_for_a_different_owner(fake_db):
    created = store.create_client(1, "Acme Corp", "acme-corp")
    assert store.get_client(created["id"], 1) is not None
    assert store.get_client(created["id"], 2) is None


def test_list_clients_only_shows_the_calling_users_own_clients(fake_db):
    store.create_client(1, "Acme Corp", "acme-corp")
    store.create_client(2, "Widgets Inc", "widgets-inc")

    user_1_clients = store.list_clients(1)
    user_2_clients = store.list_clients(2)

    assert [c["name"] for c in user_1_clients] == ["Acme Corp"]
    assert [c["name"] for c in user_2_clients] == ["Widgets Inc"]


def test_created_client_is_stamped_with_its_owner(fake_db):
    created = store.create_client(5, "Acme Corp", "acme-corp")
    assert created["owner_user_id"] == 5
