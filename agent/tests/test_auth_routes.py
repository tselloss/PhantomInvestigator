import psycopg
import pytest
from fastapi.testclient import TestClient

import main
import users
from routes import auth as auth_routes


@pytest.fixture(autouse=True)
def session_secret(monkeypatch):
    monkeypatch.setattr(auth_routes, "SESSION_SECRET", "test-secret-that-is-long-enough-for-hs256")
    # TestClient talks to "http://testserver" (no TLS) -- a Secure cookie
    # wouldn't round-trip back on the next request otherwise.
    monkeypatch.setattr(auth_routes, "SESSION_COOKIE_SECURE", False)


@pytest.fixture
def client():
    return TestClient(main.app)


def test_register_creates_user_and_sets_session_cookie(monkeypatch, client):
    monkeypatch.setattr(
        users, "create_user", lambda username, password, tos_accepted=False: {"id": 1, "username": username}
    )
    resp = client.post(
        "/auth/register", json={"username": "alice", "password": "hunter2", "accept_terms": True}
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert "phantom_session" in resp.cookies


def test_register_rejects_duplicate_username(monkeypatch, client):
    def boom(username, password, tos_accepted=False):
        raise psycopg.errors.UniqueViolation("duplicate username")

    monkeypatch.setattr(users, "create_user", boom)
    resp = client.post(
        "/auth/register", json={"username": "alice", "password": "hunter2", "accept_terms": True}
    )
    assert resp.status_code == 409


def test_register_requires_non_blank_username_and_password(client):
    resp = client.post("/auth/register", json={"username": "   ", "password": "", "accept_terms": True})
    assert resp.status_code == 400


def test_register_requires_accept_terms(monkeypatch, client):
    monkeypatch.setattr(
        users, "create_user", lambda username, password, tos_accepted=False: {"id": 1, "username": username}
    )
    resp = client.post("/auth/register", json={"username": "alice", "password": "hunter2"})
    assert resp.status_code == 400


def test_login_success_sets_session_cookie(monkeypatch, client):
    user = {"id": 5, "username": "bob", "password_hash": "hashed"}
    monkeypatch.setattr(users, "get_user_by_username", lambda username: user)
    monkeypatch.setattr(users, "verify_password", lambda u, p: True)

    resp = client.post("/auth/login", json={"username": "bob", "password": "pw"})
    assert resp.status_code == 200
    assert "phantom_session" in resp.cookies


def test_login_rejects_wrong_password(monkeypatch, client):
    user = {"id": 5, "username": "bob", "password_hash": "hashed"}
    monkeypatch.setattr(users, "get_user_by_username", lambda username: user)
    monkeypatch.setattr(users, "verify_password", lambda u, p: False)

    resp = client.post("/auth/login", json={"username": "bob", "password": "wrong"})
    assert resp.status_code == 401


def test_login_rejects_unknown_username(monkeypatch, client):
    monkeypatch.setattr(users, "get_user_by_username", lambda username: None)
    resp = client.post("/auth/login", json={"username": "ghost", "password": "pw"})
    assert resp.status_code == 401


def test_me_returns_current_user_after_login(monkeypatch, client):
    user = {"id": 5, "username": "bob", "password_hash": "hashed", "tos_accepted_at": None}
    monkeypatch.setattr(users, "get_user_by_username", lambda username: user)
    monkeypatch.setattr(users, "verify_password", lambda u, p: True)
    monkeypatch.setattr(users, "get_user_by_id", lambda user_id: user)

    client.post("/auth/login", json={"username": "bob", "password": "pw"})
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"id": 5, "username": "bob", "tos_accepted": False}


def test_me_reports_tos_accepted_true_once_set(monkeypatch, client):
    user = {"id": 5, "username": "bob", "password_hash": "hashed", "tos_accepted_at": "2026-07-11T00:00:00Z"}
    monkeypatch.setattr(users, "get_user_by_username", lambda username: user)
    monkeypatch.setattr(users, "verify_password", lambda u, p: True)
    monkeypatch.setattr(users, "get_user_by_id", lambda user_id: user)

    client.post("/auth/login", json={"username": "bob", "password": "pw"})
    resp = client.get("/auth/me")
    assert resp.json()["tos_accepted"] is True


def test_me_requires_session(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_logout_clears_session(monkeypatch, client):
    user = {"id": 5, "username": "bob", "password_hash": "hashed"}
    monkeypatch.setattr(users, "get_user_by_username", lambda username: user)
    monkeypatch.setattr(users, "verify_password", lambda u, p: True)

    client.post("/auth/login", json={"username": "bob", "password": "pw"})
    resp = client.post("/auth/logout")
    assert resp.status_code == 200

    me_resp = client.get("/auth/me")
    assert me_resp.status_code == 401


def test_accept_terms_requires_session(client):
    resp = client.post("/auth/accept-terms")
    assert resp.status_code == 401


def test_accept_terms_stamps_current_user(monkeypatch, client):
    user = {"id": 5, "username": "bob", "password_hash": "hashed", "tos_accepted_at": None}
    monkeypatch.setattr(users, "get_user_by_username", lambda username: user)
    monkeypatch.setattr(users, "verify_password", lambda u, p: True)

    calls = []
    monkeypatch.setattr(users, "accept_terms", lambda user_id: calls.append(user_id))

    client.post("/auth/login", json={"username": "bob", "password": "pw"})
    resp = client.post("/auth/accept-terms")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert calls == [5]


def test_auth_middleware_attaches_user_to_request_state(monkeypatch, client):
    """AuthMiddleware should stash the verified user on request.state.user
    for /api/* routes -- this is what get_current_user() reads. Uses the
    existing /api/settings/ai status endpoint (auth-gated, doesn't itself
    need per-user scoping to prove this) as a probe."""
    user = {"id": 5, "username": "bob", "password_hash": "hashed"}
    monkeypatch.setattr(users, "get_user_by_username", lambda username: user)
    monkeypatch.setattr(users, "verify_password", lambda u, p: True)

    client.post("/auth/login", json={"username": "bob", "password": "pw"})
    resp = client.get("/api/settings/ai")
    assert resp.status_code == 200
