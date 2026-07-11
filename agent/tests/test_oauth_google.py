import httpx
import psycopg
import pytest
import respx
from fastapi.testclient import TestClient

import main
import users
from routes import auth as auth_routes

TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


@pytest.fixture(autouse=True)
def session_secret(monkeypatch):
    monkeypatch.setattr(auth_routes, "SESSION_SECRET", "test-secret-that-is-long-enough-for-hs256")
    monkeypatch.setattr(auth_routes, "SESSION_COOKIE_SECURE", False)


@pytest.fixture(autouse=True)
def _google_unconfigured_by_default(monkeypatch):
    """Tests in this file assert both the disabled-by-default and configured
    states. Without forcing this, the "disabled" tests would inherit
    whatever real GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI happen to be set in
    the environment running the suite (e.g. a real deployment's .env with
    Google sign-in actually configured) instead of exercising the disabled
    path. google_configured below runs after this (autouse fixtures are
    instantiated first) and overrides these for the tests that need it."""
    monkeypatch.setattr(auth_routes, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(auth_routes, "GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setattr(auth_routes, "GOOGLE_REDIRECT_URI", "")


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def google_configured(monkeypatch):
    monkeypatch.setattr(auth_routes, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(auth_routes, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(auth_routes, "GOOGLE_REDIRECT_URI", "http://testserver/auth/google/callback")


def _mock_google(email="alice@example.com", sub="g-1", email_verified=True):
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "test-access-token"}))
    respx.get(USERINFO_URL).mock(
        return_value=httpx.Response(200, json={"sub": sub, "email": email, "email_verified": email_verified})
    )


def test_google_status_reports_disabled_by_default(client):
    resp = client.get("/auth/google/status")
    assert resp.json() == {"enabled": False}


def test_google_status_reports_enabled_when_configured(google_configured, client):
    resp = client.get("/auth/google/status")
    assert resp.json() == {"enabled": True}


def test_google_login_requires_config(client):
    resp = client.get("/auth/google/login")
    assert resp.status_code == 500


def test_google_login_redirects_and_sets_state_cookie(google_configured, client):
    resp = client.get("/auth/google/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "phantom_oauth_state" in resp.cookies


def test_google_callback_rejects_missing_state_cookie(google_configured, client):
    resp = client.get("/auth/google/callback", params={"code": "abc", "state": "xyz"}, follow_redirects=False)
    assert resp.headers["location"] == "/login?error=google_failed"


def test_google_callback_rejects_state_mismatch(google_configured, client):
    client.cookies.set("phantom_oauth_state", "expected-state")
    resp = client.get(
        "/auth/google/callback", params={"code": "abc", "state": "wrong-state"}, follow_redirects=False
    )
    assert resp.headers["location"] == "/login?error=google_failed"


def test_google_callback_rejects_google_error(google_configured, client):
    client.cookies.set("phantom_oauth_state", "expected-state")
    resp = client.get(
        "/auth/google/callback", params={"error": "access_denied", "state": "expected-state"}, follow_redirects=False
    )
    assert resp.headers["location"] == "/login?error=google_failed"


@respx.mock
def test_google_callback_rejects_unverified_email(google_configured, client):
    _mock_google(email_verified=False)
    client.cookies.set("phantom_oauth_state", "expected-state")
    resp = client.get(
        "/auth/google/callback", params={"code": "abc", "state": "expected-state"}, follow_redirects=False
    )
    assert resp.headers["location"] == "/login?error=google_failed"


@respx.mock
def test_google_callback_creates_new_user_and_sets_session(google_configured, client, monkeypatch):
    monkeypatch.setattr(users, "get_user_by_google_id", lambda google_id: None)
    monkeypatch.setattr(users, "get_user_by_email", lambda email: None)
    created = {}

    def fake_create_google_user(username, email, google_id):
        created.update(username=username, email=email, google_id=google_id)
        return {"id": 9, "username": username, "email": email, "google_id": google_id}

    monkeypatch.setattr(users, "create_google_user", fake_create_google_user)
    _mock_google(email="alice@example.com", sub="g-1")

    client.cookies.set("phantom_oauth_state", "expected-state")
    resp = client.get(
        "/auth/google/callback", params={"code": "abc", "state": "expected-state"}, follow_redirects=False
    )
    assert resp.headers["location"] == "/dashboard"
    assert "phantom_session" in resp.cookies
    assert created == {"username": "alice", "email": "alice@example.com", "google_id": "g-1"}


@respx.mock
def test_google_callback_logs_in_existing_google_user(google_configured, client, monkeypatch):
    existing = {"id": 5, "username": "bob", "email": "bob@example.com", "google_id": "g-5"}
    monkeypatch.setattr(users, "get_user_by_google_id", lambda google_id: existing)
    _mock_google(email="bob@example.com", sub="g-5")

    client.cookies.set("phantom_oauth_state", "expected-state")
    resp = client.get(
        "/auth/google/callback", params={"code": "abc", "state": "expected-state"}, follow_redirects=False
    )
    assert resp.headers["location"] == "/dashboard"
    assert "phantom_session" in resp.cookies


@respx.mock
def test_google_callback_links_existing_password_account_by_email(google_configured, client, monkeypatch):
    monkeypatch.setattr(users, "get_user_by_google_id", lambda google_id: None)
    existing = {"id": 7, "username": "carol", "email": "carol@example.com", "google_id": None}
    monkeypatch.setattr(users, "get_user_by_email", lambda email: existing)
    linked = {}
    monkeypatch.setattr(
        users, "link_google_id", lambda user_id, google_id: linked.update(user_id=user_id, google_id=google_id)
    )
    _mock_google(email="carol@example.com", sub="g-7")

    client.cookies.set("phantom_oauth_state", "expected-state")
    resp = client.get(
        "/auth/google/callback", params={"code": "abc", "state": "expected-state"}, follow_redirects=False
    )
    assert resp.headers["location"] == "/dashboard"
    assert linked == {"user_id": 7, "google_id": "g-7"}


@respx.mock
def test_google_callback_retries_username_on_collision(google_configured, client, monkeypatch):
    monkeypatch.setattr(users, "get_user_by_google_id", lambda google_id: None)
    monkeypatch.setattr(users, "get_user_by_email", lambda email: None)
    calls = []

    def fake_create_google_user(username, email, google_id):
        calls.append(username)
        if len(calls) == 1:
            raise psycopg.errors.UniqueViolation("duplicate username")
        return {"id": 11, "username": username, "email": email, "google_id": google_id}

    monkeypatch.setattr(users, "create_google_user", fake_create_google_user)
    _mock_google(email="dave@example.com", sub="g-99")

    client.cookies.set("phantom_oauth_state", "expected-state")
    resp = client.get(
        "/auth/google/callback", params={"code": "abc", "state": "expected-state"}, follow_redirects=False
    )
    assert resp.headers["location"] == "/dashboard"
    assert len(calls) == 2
    assert calls[0] == "dave"
    assert calls[1].startswith("dave-")
