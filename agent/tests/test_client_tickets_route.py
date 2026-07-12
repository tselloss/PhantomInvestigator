import pytest
from fastapi.testclient import TestClient

import main
from routes import client_tickets


@pytest.fixture(autouse=True)
def bypass_auth(monkeypatch):
    monkeypatch.setattr(main, "verify_session_cookie", lambda token: {"user_id": 1, "username": "test-operator"})
    monkeypatch.setattr(main, "user_tos_accepted", lambda user_id: True)


client = TestClient(main.app)

CLIENT = {"id": 7, "name": "Acme Corp", "slug": "acme-corp", "notes": None, "created_at": "2026-01-01T00:00:00Z", "archived_at": None}


def test_list_client_tickets_404_for_unknown_client(monkeypatch):
    monkeypatch.setattr(client_tickets.clients, "get_client", lambda client_id, owner_user_id: None)
    resp = client.get("/api/clients/999/tickets")
    assert resp.status_code == 404


def test_list_client_tickets_delegates(monkeypatch):
    monkeypatch.setattr(client_tickets.clients, "get_client", lambda client_id, owner_user_id: CLIENT)
    captured = {}

    def fake_recent(client_id, user_id, days=30):
        captured.update(client_id=client_id, user_id=user_id, days=days)
        return [{"source": "jira", "id": "OPS-1", "title": "x", "type": "Bug", "status": "Open", "updated": "2026-07-10T00:00:00Z", "url": None}]

    monkeypatch.setattr(client_tickets.integration_settings, "client_recent_tickets", fake_recent)
    resp = client.get("/api/clients/7/tickets")
    assert resp.status_code == 200
    assert resp.json()[0]["source"] == "jira"
    assert captured == {"client_id": 7, "user_id": 1, "days": 30}


def test_list_client_tickets_passes_days_query_param(monkeypatch):
    monkeypatch.setattr(client_tickets.clients, "get_client", lambda client_id, owner_user_id: CLIENT)
    captured = {}

    def fake_recent(client_id, user_id, days=30):
        captured["days"] = days
        return []

    monkeypatch.setattr(client_tickets.integration_settings, "client_recent_tickets", fake_recent)
    resp = client.get("/api/clients/7/tickets?days=7")
    assert resp.status_code == 200
    assert captured["days"] == 7
