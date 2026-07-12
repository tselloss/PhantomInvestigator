import pytest
from fastapi.testclient import TestClient

import main
from routes import client_integrations


@pytest.fixture(autouse=True)
def bypass_auth(monkeypatch):
    monkeypatch.setattr(main, "verify_session_cookie", lambda token: {"user_id": 1, "username": "test-operator"})
    monkeypatch.setattr(main, "user_tos_accepted", lambda user_id: True)


client = TestClient(main.app)

CLIENT = {"id": 7, "name": "Acme Corp", "slug": "acme-corp", "notes": None, "created_at": "2026-01-01T00:00:00Z", "archived_at": None}


def test_list_client_integrations_404_for_unknown_client(monkeypatch):
    monkeypatch.setattr(client_integrations.clients, "get_client", lambda client_id, owner_user_id: None)
    resp = client.get("/api/clients/999/integrations")
    assert resp.status_code == 404


def test_list_client_integrations_delegates(monkeypatch):
    monkeypatch.setattr(client_integrations.clients, "get_client", lambda client_id, owner_user_id: CLIENT)
    monkeypatch.setattr(
        client_integrations.integration_settings, "client_integration_status",
        lambda client_id, user_id: [{"name": "jira", "configured": False, "editable": True, "override": False, "using_global_default": False}],
    )
    resp = client.get("/api/clients/7/integrations")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "jira"


def test_set_client_integration_404_for_unknown_client(monkeypatch):
    monkeypatch.setattr(client_integrations.clients, "get_client", lambda client_id, owner_user_id: None)
    resp = client.post("/api/clients/999/integrations/jira", json={"api_token": "x"})
    assert resp.status_code == 404


def test_set_client_integration_delegates(monkeypatch):
    monkeypatch.setattr(client_integrations.clients, "get_client", lambda client_id, owner_user_id: CLIENT)
    captured = {}

    def fake_set(client_id, user_id, name, fields):
        captured.update(client_id=client_id, user_id=user_id, name=name, fields=fields)
        return {"name": name, "configured": True, "override": True}

    monkeypatch.setattr(client_integrations.integration_settings, "set_client_integration", fake_set)
    resp = client.post("/api/clients/7/integrations/jira", json={"api_token": "abc"})
    assert resp.status_code == 200
    assert captured == {"client_id": 7, "user_id": 1, "name": "jira", "fields": {"api_token": "abc"}}


def test_set_client_integration_rejects_unknown_integration(monkeypatch):
    monkeypatch.setattr(client_integrations.clients, "get_client", lambda client_id, owner_user_id: CLIENT)

    def fake_set(client_id, user_id, name, fields):
        raise ValueError(f"'{name}' has no editable credential fields")

    monkeypatch.setattr(client_integrations.integration_settings, "set_client_integration", fake_set)
    resp = client.post("/api/clients/7/integrations/not-real", json={})
    assert resp.status_code == 404


def test_clear_client_integration_404_for_unknown_client(monkeypatch):
    monkeypatch.setattr(client_integrations.clients, "get_client", lambda client_id, owner_user_id: None)
    resp = client.delete("/api/clients/999/integrations/jira")
    assert resp.status_code == 404


def test_clear_client_integration_delegates(monkeypatch):
    monkeypatch.setattr(client_integrations.clients, "get_client", lambda client_id, owner_user_id: CLIENT)
    captured = {}

    def fake_clear(client_id, user_id, name):
        captured.update(client_id=client_id, user_id=user_id, name=name)
        return {"name": name, "configured": False, "override": False}

    monkeypatch.setattr(client_integrations.integration_settings, "clear_client_integration", fake_clear)
    resp = client.delete("/api/clients/7/integrations/jira")
    assert resp.status_code == 200
    assert captured == {"client_id": 7, "user_id": 1, "name": "jira"}


def test_test_client_integration_404_for_unknown_client(monkeypatch):
    monkeypatch.setattr(client_integrations.clients, "get_client", lambda client_id, owner_user_id: None)
    resp = client.post("/api/clients/999/integrations/jira/test")
    assert resp.status_code == 404


def test_test_client_integration_404_for_unknown_integration(monkeypatch):
    monkeypatch.setattr(client_integrations.clients, "get_client", lambda client_id, owner_user_id: CLIENT)
    resp = client.post("/api/clients/7/integrations/not-real/test")
    assert resp.status_code == 404


def test_test_client_integration_delegates(monkeypatch):
    monkeypatch.setattr(client_integrations.clients, "get_client", lambda client_id, owner_user_id: CLIENT)
    monkeypatch.setattr(
        client_integrations.integration_settings, "test_client_integration",
        lambda client_id, user_id, name: {"ok": True, "detail": "reachable"},
    )
    resp = client.post("/api/clients/7/integrations/jira/test")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "detail": "reachable"}
