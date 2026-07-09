import pytest
from fastapi.testclient import TestClient

import main
from routes import investigations


@pytest.fixture(autouse=True)
def bypass_auth(monkeypatch):
    """/api/* is session-gated by main.AuthMiddleware; these tests exercise
    the investigations routes themselves, not the login flow, so bypass it
    the same way a valid session cookie would."""
    monkeypatch.setattr(main, "verify_session_cookie", lambda token: {"user_id": 1, "username": "test-operator"})


client = TestClient(main.app)


def test_list_investigations_passes_deployment_id_filter(monkeypatch):
    captured = {}

    def fake_list_recent(owner_user_id, **kwargs):
        captured.update(owner_user_id=owner_user_id, **kwargs)
        return []

    monkeypatch.setattr(investigations.store, "list_recent", fake_list_recent)
    resp = client.get("/api/investigations", params={"deployment_id": 42})
    assert resp.status_code == 200
    assert captured["owner_user_id"] == 1
    assert captured["deployment_id"] == 42


def test_list_investigations_omits_deployment_id_when_not_given(monkeypatch):
    captured = {}

    def fake_list_recent(owner_user_id, **kwargs):
        captured.update(owner_user_id=owner_user_id, **kwargs)
        return []

    monkeypatch.setattr(investigations.store, "list_recent", fake_list_recent)
    resp = client.get("/api/investigations")
    assert resp.status_code == 200
    assert captured["deployment_id"] is None


def test_stats_passes_deployment_id_and_days(monkeypatch):
    captured = {}

    def fake_stats(owner_user_id, **kwargs):
        captured.update(owner_user_id=owner_user_id, **kwargs)
        return {"total": 0, "by_status": {}, "total_cost_usd": 0.0, "period_days": kwargs["days"]}

    monkeypatch.setattr(investigations.store, "stats", fake_stats)
    resp = client.get("/api/investigations/stats", params={"deployment_id": 42, "days": 3})
    assert resp.status_code == 200
    assert captured == {"owner_user_id": 1, "days": 3, "deployment_id": 42}


def test_stats_defaults_deployment_id_to_none(monkeypatch):
    captured = {}

    def fake_stats(owner_user_id, **kwargs):
        captured.update(owner_user_id=owner_user_id, **kwargs)
        return {"total": 0, "by_status": {}, "total_cost_usd": 0.0, "period_days": kwargs["days"]}

    monkeypatch.setattr(investigations.store, "stats", fake_stats)
    resp = client.get("/api/investigations/stats")
    assert resp.status_code == 200
    assert captured == {"owner_user_id": 1, "days": 7, "deployment_id": None}
