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
        if sql.startswith("INSERT INTO users (username, password_hash)"):
            username, password_hash = params
            if username in self.table:
                raise psycopg.errors.UniqueViolation("duplicate username")
            row = (self._next_id, username, password_hash, "2024-01-01T00:00:00Z", None, None, None, False)
            self.table[username] = row
            self._next_id += 1
            self._result = row
        elif sql.startswith("INSERT INTO users (username, email, google_id)"):
            username, email, google_id = params
            if username in self.table:
                raise psycopg.errors.UniqueViolation("duplicate username")
            row = (self._next_id, username, None, "2024-01-01T00:00:00Z", email, google_id, None, False)
            self.table[username] = row
            self._next_id += 1
            self._result = row
        elif sql.startswith("UPDATE users SET google_id"):
            google_id, user_id = params
            for uname, row in self.table.items():
                if row[0] == user_id:
                    self.table[uname] = row[:5] + (google_id,) + row[6:]
                    break
            self._result = None
        elif sql.startswith("UPDATE users SET monthly_limit_usd"):
            limit_usd, user_id = params
            for uname, row in self.table.items():
                if row[0] == user_id:
                    self.table[uname] = row[:6] + (limit_usd,) + row[7:]
                    break
            self._result = None
        elif sql.startswith("UPDATE users SET demo_mode"):
            enabled, user_id = params
            for uname, row in self.table.items():
                if row[0] == user_id:
                    self.table[uname] = row[:7] + (enabled,)
                    break
            self._result = None
        elif "FROM users WHERE username" in sql:
            (username,) = params
            self._result = self.table.get(username)
        elif "FROM users WHERE id" in sql:
            (user_id,) = params
            self._result = next((r for r in self.table.values() if r[0] == user_id), None)
        elif "FROM users WHERE google_id" in sql:
            (google_id,) = params
            self._result = next((r for r in self.table.values() if r[5] == google_id), None)
        elif "FROM users WHERE email" in sql:
            (email,) = params
            self._result = next((r for r in self.table.values() if r[4] == email), None)
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


def test_create_google_user_then_get_by_google_id(fake_db):
    created = users.create_google_user("alice", "alice@example.com", "g-1")
    assert created["username"] == "alice"
    assert created["password_hash"] is None

    fetched = users.get_user_by_google_id("g-1")
    assert fetched["id"] == created["id"]
    assert fetched["email"] == "alice@example.com"


def test_create_google_user_rejects_duplicate_username(fake_db):
    users.create_user("alice", "hunter2")
    with pytest.raises(psycopg.errors.UniqueViolation):
        users.create_google_user("alice", "alice@example.com", "g-1")


def test_get_user_by_email(fake_db):
    users.create_google_user("bob", "bob@example.com", "g-2")
    fetched = users.get_user_by_email("bob@example.com")
    assert fetched["username"] == "bob"


def test_get_user_by_email_none_when_missing(fake_db):
    assert users.get_user_by_email("nobody@example.com") is None


def test_get_user_by_google_id_none_when_missing(fake_db):
    assert users.get_user_by_google_id("nope") is None


def test_link_google_id_updates_existing_user(fake_db):
    created = users.create_user("carol", "hunter2")
    users.link_google_id(created["id"], "g-3")
    fetched = users.get_user_by_google_id("g-3")
    assert fetched["id"] == created["id"]


def test_verify_password_false_when_no_password_hash(fake_db):
    google_user = users.create_google_user("dave", "dave@example.com", "g-4")
    assert users.verify_password(google_user, "anything") is False


def test_update_monthly_limit_sets_value(fake_db):
    created = users.create_user("erin", "hunter2")
    assert created["monthly_limit_usd"] is None

    users.update_monthly_limit(created["id"], 10.5)
    fetched = users.get_user_by_id(created["id"])
    assert fetched["monthly_limit_usd"] == 10.5


def test_update_monthly_limit_can_clear_to_none(fake_db):
    created = users.create_user("frank", "hunter2")
    users.update_monthly_limit(created["id"], 10.5)

    users.update_monthly_limit(created["id"], None)
    fetched = users.get_user_by_id(created["id"])
    assert fetched["monthly_limit_usd"] is None


def test_get_demo_mode_defaults_false(fake_db):
    created = users.create_user("grace", "hunter2")
    assert users.get_demo_mode(created["id"]) is False


def test_get_demo_mode_false_for_unknown_user(fake_db):
    assert users.get_demo_mode(999) is False


def test_update_demo_mode_enables_and_disables(fake_db):
    created = users.create_user("heidi", "hunter2")

    users.update_demo_mode(created["id"], True)
    assert users.get_demo_mode(created["id"]) is True

    users.update_demo_mode(created["id"], False)
    assert users.get_demo_mode(created["id"]) is False


def test_update_demo_mode_does_not_disturb_monthly_limit(fake_db):
    created = users.create_user("ivan", "hunter2")
    users.update_monthly_limit(created["id"], 10.5)

    users.update_demo_mode(created["id"], True)
    fetched = users.get_user_by_id(created["id"])
    assert fetched["monthly_limit_usd"] == 10.5
    assert fetched["demo_mode"] is True
