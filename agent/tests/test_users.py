import psycopg
import pytest

import users


class _FakeConn:
    """Mirrors the mock-the-DB-layer pattern used by
    test_integration_credentials.py -- an in-memory dict standing in for the
    users table, keyed by username."""

    def __init__(self, table):
        self.table = table
        self._next_id = max([r[0] for r in table.values()], default=0) + 1
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        sql = " ".join(sql.split())
        if sql.startswith("INSERT INTO users"):
            username, password_hash = params
            if username in self.table:
                raise psycopg.errors.UniqueViolation("duplicate username")
            row = (self._next_id, username, password_hash, "2024-01-01T00:00:00Z")
            self.table[username] = row
            self._next_id += 1
            self._result = row
        elif "FROM users WHERE username" in sql:
            (username,) = params
            self._result = self.table.get(username)
        elif "FROM users WHERE id" in sql:
            (user_id,) = params
            self._result = next((r for r in self.table.values() if r[0] == user_id), None)
        else:
            raise AssertionError(f"unexpected SQL in fake connection: {sql!r}")
        return self

    def fetchone(self):
        return self._result


@pytest.fixture
def fake_db(monkeypatch):
    table = {}
    monkeypatch.setattr(users, "_connect", lambda: _FakeConn(table))
    return table


def test_create_user_then_get_by_username(fake_db):
    created = users.create_user("alice", "hunter2")
    assert created["username"] == "alice"

    fetched = users.get_user_by_username("alice")
    assert fetched["id"] == created["id"]
    assert fetched["password_hash"] != "hunter2"  # hashed, never stored in plaintext


def test_create_user_rejects_duplicate_username(fake_db):
    users.create_user("alice", "hunter2")
    with pytest.raises(psycopg.errors.UniqueViolation):
        users.create_user("alice", "different-password")


def test_get_user_by_username_none_when_missing(fake_db):
    assert users.get_user_by_username("nobody") is None


def test_get_user_by_id(fake_db):
    created = users.create_user("bob", "pw")
    fetched = users.get_user_by_id(created["id"])
    assert fetched["username"] == "bob"


def test_get_user_by_id_none_when_missing(fake_db):
    assert users.get_user_by_id(999) is None


def test_verify_password_correct(fake_db):
    created = users.create_user("carol", "correct-horse-battery-staple")
    assert users.verify_password(created, "correct-horse-battery-staple") is True


def test_verify_password_incorrect(fake_db):
    created = users.create_user("carol", "correct-horse-battery-staple")
    assert users.verify_password(created, "wrong-password") is False
