import pytest
from fastapi.testclient import TestClient

import main
from routes import clients


@pytest.fixture(autouse=True)
def bypass_auth(monkeypatch):
    """/api/* is session-gated by main.AuthMiddleware; these tests exercise
    the clients routes themselves, not the login flow, so bypass it the same
    way a valid session cookie would."""
    monkeypatch.setattr(main, "verify_session_cookie", lambda token: {"user_id": 1, "username": "test-operator"})


client = TestClient(main.app)

CLIENT = {
    "id": 7, "name": "Acme Corp", "slug": "acme-corp", "notes": None,
    "created_at": "2026-01-01T00:00:00Z", "archived_at": None,
}
DEPLOYMENT = {
    "id": 42, "client_id": 7, "label": "prod", "environment": "production",
    "jira_project_key": None, "github_repo": None, "checkin_token": "tok",
    "created_at": "2026-01-01T00:00:00Z", "archived_at": None,
}


def test_update_client_404_for_unknown(monkeypatch):
    monkeypatch.setattr(clients.store, "update_client", lambda *a, **kw: None)
    resp = client.patch("/api/clients/999", json={"name": "New name"})
    assert resp.status_code == 404


def test_update_client_passes_fields_through(monkeypatch):
    captured = {}

    def fake_update(client_id, owner_user_id, name, notes):
        captured.update(client_id=client_id, owner_user_id=owner_user_id, name=name, notes=notes)
        return {**CLIENT, "name": name, "notes": notes}

    monkeypatch.setattr(clients.store, "update_client", fake_update)
    resp = client.patch("/api/clients/7", json={"name": "Acme Renamed", "notes": "VIP"})
    assert resp.status_code == 200
    assert captured == {"client_id": 7, "owner_user_id": 1, "name": "Acme Renamed", "notes": "VIP"}
    assert resp.json()["name"] == "Acme Renamed"


def test_archive_client_404_for_unknown(monkeypatch):
    monkeypatch.setattr(clients.store, "archive_client", lambda client_id, owner_user_id: None)
    assert client.delete("/api/clients/999").status_code == 404


def test_archive_client_delegates(monkeypatch):
    monkeypatch.setattr(
        clients.store, "archive_client",
        lambda client_id, owner_user_id: {**CLIENT, "archived_at": "2026-07-08T00:00:00Z"},
    )
    resp = client.delete("/api/clients/7")
    assert resp.status_code == 200
    assert resp.json()["archived_at"] == "2026-07-08T00:00:00Z"


def test_update_deployment_404_when_owned_by_different_client(monkeypatch):
    monkeypatch.setattr(clients.store, "get_deployment", lambda deployment_id, owner_user_id: DEPLOYMENT)
    resp = client.patch("/api/clients/999/deployments/42", json={"label": "prod"})
    assert resp.status_code == 404


def test_update_deployment_delegates(monkeypatch):
    monkeypatch.setattr(clients.store, "get_deployment", lambda deployment_id, owner_user_id: DEPLOYMENT)
    monkeypatch.setattr(clients.store, "update_deployment", lambda *a, **kw: {**DEPLOYMENT, "label": "prod-eu"})
    resp = client.patch(
        "/api/clients/7/deployments/42",
        json={"label": "prod-eu", "environment": "production", "jira_project_key": "OPS", "github_repo": "acme/app"},
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "prod-eu"


def test_update_deployment_passes_allowed_base_branches_through(monkeypatch):
    monkeypatch.setattr(clients.store, "get_deployment", lambda deployment_id, owner_user_id: DEPLOYMENT)
    captured = {}

    def fake_update(deployment_id, owner_user_id, label, environment, jira_project_key, github_repo, azure_devops_project, allowed_base_branches):
        captured.update(allowed_base_branches=allowed_base_branches)
        return {**DEPLOYMENT, "allowed_base_branches": allowed_base_branches}

    monkeypatch.setattr(clients.store, "update_deployment", fake_update)
    resp = client.patch(
        "/api/clients/7/deployments/42",
        json={"label": "prod", "allowed_base_branches": ["main", "staging"]},
    )
    assert resp.status_code == 200
    assert captured["allowed_base_branches"] == ["main", "staging"]
    assert resp.json()["allowed_base_branches"] == ["main", "staging"]


def test_create_deployment_passes_allowed_base_branches_through(monkeypatch):
    monkeypatch.setattr(clients.store, "get_client", lambda client_id, owner_user_id: CLIENT)
    captured = {}

    def fake_create(client_id, owner_user_id, label, environment, jira_project_key, github_repo, azure_devops_project, allowed_base_branches):
        captured.update(allowed_base_branches=allowed_base_branches)
        return {**DEPLOYMENT, "allowed_base_branches": allowed_base_branches}

    monkeypatch.setattr(clients.store, "create_deployment", fake_create)
    resp = client.post(
        "/api/clients/7/deployments",
        json={"label": "prod", "allowed_base_branches": ["main"]},
    )
    assert resp.status_code == 200
    assert captured["allowed_base_branches"] == ["main"]


def test_archive_deployment_404_when_owned_by_different_client(monkeypatch):
    monkeypatch.setattr(clients.store, "get_deployment", lambda deployment_id, owner_user_id: DEPLOYMENT)
    resp = client.delete("/api/clients/999/deployments/42")
    assert resp.status_code == 404


def test_archive_deployment_delegates(monkeypatch):
    monkeypatch.setattr(clients.store, "get_deployment", lambda deployment_id, owner_user_id: DEPLOYMENT)
    monkeypatch.setattr(
        clients.store, "archive_deployment",
        lambda deployment_id, owner_user_id: {**DEPLOYMENT, "archived_at": "2026-07-08T00:00:00Z"},
    )
    resp = client.delete("/api/clients/7/deployments/42")
    assert resp.status_code == 200
    assert resp.json()["archived_at"] == "2026-07-08T00:00:00Z"


def test_list_all_deployments_excludes_deployments_of_archived_client(monkeypatch):
    archived_client = {**CLIENT, "id": 8, "name": "Retired Co", "archived_at": "2026-06-01T00:00:00Z"}
    other_deployment = {**DEPLOYMENT, "id": 43, "client_id": 8, "archived_at": None}

    monkeypatch.setattr(
        clients.store, "list_clients",
        lambda owner_user_id, include_archived=False: [CLIENT, archived_client] if include_archived else [CLIENT],
    )
    monkeypatch.setattr(
        clients.store, "list_deployments",
        lambda owner_user_id, include_archived=False: [DEPLOYMENT, other_deployment],
    )

    resp = client.get("/api/clients/deployments")
    assert resp.status_code == 200
    assert [d["id"] for d in resp.json()] == [42]


def test_list_all_deployments_include_archived_shows_everything(monkeypatch):
    archived_client = {**CLIENT, "id": 8, "name": "Retired Co", "archived_at": "2026-06-01T00:00:00Z"}
    other_deployment = {**DEPLOYMENT, "id": 43, "client_id": 8, "archived_at": None}

    monkeypatch.setattr(
        clients.store, "list_clients",
        lambda owner_user_id, include_archived=False: [CLIENT, archived_client] if include_archived else [CLIENT],
    )
    monkeypatch.setattr(
        clients.store, "list_deployments",
        lambda owner_user_id, include_archived=False: [DEPLOYMENT, other_deployment],
    )

    resp = client.get("/api/clients/deployments", params={"include_archived": "true"})
    assert resp.status_code == 200
    assert sorted(d["id"] for d in resp.json()) == [42, 43]
