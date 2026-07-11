import pytest
from fastapi.testclient import TestClient

import main
import rate_limit
import users
from routes import auth as auth_routes
from routes import webhooks


@pytest.fixture(autouse=True)
def session_secret(monkeypatch):
    monkeypatch.setattr(auth_routes, "SESSION_SECRET", "test-secret-that-is-long-enough-for-hs256")
    monkeypatch.setattr(auth_routes, "SESSION_COOKIE_SECURE", False)


@pytest.fixture
def client():
    return TestClient(main.app)


def test_login_allows_up_to_the_limit(monkeypatch, client):
    monkeypatch.setattr(users, "get_user_by_username", lambda username: None)

    for _ in range(rate_limit._AUTH_LIMIT):
        resp = client.post("/auth/login", json={"username": "ghost", "password": "wrong"})
        assert resp.status_code == 401  # unknown user, not yet rate-limited

    resp = client.post("/auth/login", json={"username": "ghost", "password": "wrong"})
    assert resp.status_code == 429


def test_login_rate_limit_does_not_affect_other_paths(monkeypatch, client):
    monkeypatch.setattr(users, "get_user_by_username", lambda username: None)

    for _ in range(rate_limit._AUTH_LIMIT + 5):
        client.post("/auth/login", json={"username": "ghost", "password": "wrong"})

    resp = client.get("/health")
    assert resp.status_code == 200


def test_webhook_allows_up_to_the_limit(monkeypatch, client):
    monkeypatch.setattr(webhooks, "JIRA_WEBHOOK_SECRET", "s3cr3t")

    for _ in range(rate_limit._WEBHOOK_LIMIT):
        resp = client.post("/webhooks/jira?secret=wrong", json={"issue": {"key": "OPS-1", "fields": {}}})
        assert resp.status_code == 401  # bad secret, not yet rate-limited

    resp = client.post("/webhooks/jira?secret=wrong", json={"issue": {"key": "OPS-1", "fields": {}}})
    assert resp.status_code == 429
