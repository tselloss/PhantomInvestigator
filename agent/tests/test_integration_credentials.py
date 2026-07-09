import pytest
from cryptography.fernet import Fernet
from structlog.testing import capture_logs

import integration_credentials as creds


class _FakeConn:
    """Stands in for the psycopg connection integration_credentials.py
    opens per call, backed by a plain dict instead of a real Postgres
    instance -- mirrors the mock-the-DB-layer pattern used by the other
    route/tool tests in this suite."""

    def __init__(self, table, client_table=None):
        self.table = table
        self.client_table = client_table if client_table is not None else {}
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        sql = " ".join(sql.split())
        if sql.startswith("SELECT 1 FROM integration_credentials"):
            user_id, name = params
            self._result = (1,) if (user_id, name) in self.table else None
        elif sql.startswith("SELECT encrypted_fields FROM integration_credentials"):
            user_id, name = params
            key = (user_id, name)
            self._result = (self.table[key],) if key in self.table else None
        elif sql.startswith("INSERT INTO integration_credentials"):
            user_id, name, encrypted = params
            self.table[(user_id, name)] = encrypted
            self._result = None
        elif sql.startswith("DELETE FROM integration_credentials"):
            user_id, name = params
            self.table.pop((user_id, name), None)
            self._result = None
        elif sql.startswith("SELECT 1 FROM client_integration_credentials"):
            client_id, user_id, name = params
            self._result = (1,) if (client_id, user_id, name) in self.client_table else None
        elif sql.startswith("SELECT encrypted_fields FROM client_integration_credentials"):
            client_id, user_id, name = params
            key = (client_id, user_id, name)
            self._result = (self.client_table[key],) if key in self.client_table else None
        elif sql.startswith("INSERT INTO client_integration_credentials"):
            client_id, user_id, name, encrypted = params
            self.client_table[(client_id, user_id, name)] = encrypted
            self._result = None
        elif sql.startswith("DELETE FROM client_integration_credentials"):
            client_id, user_id, name = params
            self.client_table.pop((client_id, user_id, name), None)
            self._result = None
        else:
            raise AssertionError(f"unexpected SQL in fake connection: {sql!r}")
        return self

    def fetchone(self):
        return self._result


@pytest.fixture
def fake_db(monkeypatch):
    table = {}
    client_table = {}
    monkeypatch.setattr(creds, "_connect", lambda: _FakeConn(table, client_table))
    return table


@pytest.fixture
def encryption_key(monkeypatch):
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())


def test_round_trip(fake_db, encryption_key):
    creds.set_credentials(1, "jira", {"api_token": "abc123", "email": "ops@example.com"})
    assert creds.get_credentials(1, "jira") == {"api_token": "abc123", "email": "ops@example.com"}


def test_set_credentials_merges_and_drops_empty_fields(fake_db, encryption_key):
    creds.set_credentials(1, "jira", {"api_token": "abc123", "email": "ops@example.com"})
    creds.set_credentials(1, "jira", {"api_token": "rotated-token", "email": ""})
    assert creds.get_credentials(1, "jira") == {"api_token": "rotated-token", "email": "ops@example.com"}


def test_get_credentials_none_and_warns_without_key(fake_db, monkeypatch):
    monkeypatch.delenv("CREDENTIALS_ENCRYPTION_KEY", raising=False)
    with capture_logs() as logs:
        result = creds.get_credentials(1, "jira")
    assert result is None
    assert any(entry["event"] == "integration_credentials.key_not_configured" for entry in logs)


def test_get_credentials_none_and_warns_on_wrong_key(fake_db, encryption_key):
    creds.set_credentials(1, "jira", {"api_token": "abc123"})
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())
        with capture_logs() as logs:
            result = creds.get_credentials(1, "jira")
    assert result is None
    assert any(entry["event"] == "integration_credentials.decrypt_failed" for entry in logs)


def test_has_override_false_on_db_error(monkeypatch):
    def boom():
        raise RuntimeError("db unreachable")

    monkeypatch.setattr(creds, "_connect", boom)
    assert creds.has_override(1, "jira") is False


def test_clear_credentials_removes_stored_row(fake_db, encryption_key):
    creds.set_credentials(1, "jira", {"api_token": "abc123"})
    assert creds.has_override(1, "jira") is True

    creds.clear_credentials(1, "jira")

    assert creds.has_override(1, "jira") is False
    assert creds.get_credentials(1, "jira") is None


def test_credentials_scoped_per_user(fake_db, encryption_key):
    creds.set_credentials(1, "jira", {"api_token": "user-1-token"})
    creds.set_credentials(2, "jira", {"api_token": "user-2-token"})

    assert creds.get_credentials(1, "jira") == {"api_token": "user-1-token"}
    assert creds.get_credentials(2, "jira") == {"api_token": "user-2-token"}


def test_client_credentials_round_trip(fake_db, encryption_key):
    creds.set_client_credentials(7, 1, "jira", {"api_token": "client-token"})
    assert creds.get_client_credentials(7, 1, "jira") == {"api_token": "client-token"}
    assert creds.has_client_override(7, 1, "jira") is True


def test_client_credentials_scoped_per_client_and_name(fake_db, encryption_key):
    creds.set_client_credentials(7, 1, "jira", {"api_token": "client-7-token"})
    creds.set_client_credentials(8, 1, "jira", {"api_token": "client-8-token"})
    creds.set_client_credentials(7, 1, "github", {"token": "client-7-github"})

    assert creds.get_client_credentials(7, 1, "jira") == {"api_token": "client-7-token"}
    assert creds.get_client_credentials(8, 1, "jira") == {"api_token": "client-8-token"}
    assert creds.get_client_credentials(7, 1, "github") == {"token": "client-7-github"}
    assert creds.get_client_credentials(9, 1, "jira") is None


def test_client_credentials_scoped_per_user(fake_db, encryption_key):
    """Even the same client_id shouldn't resolve under a different user_id --
    defense in depth against a caller that forgot to validate ownership."""
    creds.set_client_credentials(7, 1, "jira", {"api_token": "owner-token"})
    assert creds.get_client_credentials(7, 2, "jira") is None


def test_clear_client_credentials_removes_only_that_row(fake_db, encryption_key):
    creds.set_client_credentials(7, 1, "jira", {"api_token": "client-token"})
    creds.set_client_credentials(8, 1, "jira", {"api_token": "other-client-token"})

    creds.clear_client_credentials(7, 1, "jira")

    assert creds.has_client_override(7, 1, "jira") is False
    assert creds.get_client_credentials(8, 1, "jira") == {"api_token": "other-client-token"}


def test_resolve_credentials_prefers_client_override_over_global(fake_db, encryption_key):
    creds.set_credentials(1, "jira", {"api_token": "global-token"})
    creds.set_client_credentials(7, 1, "jira", {"api_token": "client-token"})
    assert creds.resolve_credentials("jira", 1, client_id=7) == {"api_token": "client-token"}


def test_resolve_credentials_falls_back_to_global_without_client_override(fake_db, encryption_key):
    creds.set_credentials(1, "jira", {"api_token": "global-token"})
    assert creds.resolve_credentials("jira", 1, client_id=7) == {"api_token": "global-token"}


def test_resolve_credentials_none_when_neither_configured(fake_db, encryption_key):
    assert creds.resolve_credentials("jira", 1, client_id=7) is None
    assert creds.resolve_credentials("jira", 1) is None


def test_resolve_credentials_resolves_client_id_from_deployment_id(fake_db, encryption_key, monkeypatch):
    import clients

    creds.set_client_credentials(7, 1, "jira", {"api_token": "client-token"})
    monkeypatch.setattr(clients, "get_deployment", lambda deployment_id, owner_user_id: {"id": 42, "client_id": 7})
    assert creds.resolve_credentials("jira", 1, deployment_id=42) == {"api_token": "client-token"}


def test_resolve_credentials_falls_back_to_global_when_deployment_unknown(fake_db, encryption_key, monkeypatch):
    import clients

    creds.set_credentials(1, "jira", {"api_token": "global-token"})
    monkeypatch.setattr(clients, "get_deployment", lambda deployment_id, owner_user_id: None)
    assert creds.resolve_credentials("jira", 1, deployment_id=999) == {"api_token": "global-token"}


def test_resolve_credentials_client_id_wins_over_deployment_id(fake_db, encryption_key, monkeypatch):
    import clients

    creds.set_client_credentials(7, 1, "jira", {"api_token": "client-7-token"})
    creds.set_client_credentials(8, 1, "jira", {"api_token": "client-8-token"})
    monkeypatch.setattr(clients, "get_deployment", lambda deployment_id, owner_user_id: {"id": 42, "client_id": 7})
    assert creds.resolve_credentials("jira", 1, deployment_id=42, client_id=8) == {"api_token": "client-8-token"}


def test_resolve_credentials_deployment_belonging_to_different_user_falls_back_to_own_global(fake_db, encryption_key, monkeypatch):
    """The cross-tenant leak this is meant to close: a deployment_id from a
    tool call that doesn't belong to the current investigation's owner must
    never resolve to some other user's client-scoped credentials."""
    import clients

    creds.set_credentials(1, "jira", {"api_token": "user-1-own-global-token"})
    creds.set_client_credentials(7, 2, "jira", {"api_token": "user-2-client-token"})
    # get_deployment is itself owner-scoped -- a deployment belonging to user 2
    # looked up with user 1's id returns None, exactly like the real function.
    monkeypatch.setattr(clients, "get_deployment", lambda deployment_id, owner_user_id: None)

    assert creds.resolve_credentials("jira", 1, deployment_id=42) == {"api_token": "user-1-own-global-token"}
