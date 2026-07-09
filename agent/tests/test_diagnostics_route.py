from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main
from routes import diagnostics

DEPLOYMENT = {"id": 42, "client_id": 7, "label": "prod"}


@pytest.fixture(autouse=True)
def bypass_auth(monkeypatch):
    """/api/* is session-gated by main.AuthMiddleware; these tests exercise
    the diagnostics routes themselves, not the login flow, so bypass it the
    same way a valid session cookie would."""
    monkeypatch.setattr(main, "verify_session_cookie", lambda token: {"user_id": 1, "username": "test-operator"})


client = TestClient(main.app)


def test_upload_rejects_unknown_deployment(monkeypatch):
    monkeypatch.setattr(diagnostics.clients, "get_deployment", lambda deployment_id, owner_user_id: None)
    resp = client.post("/api/diagnostics/upload", data={"deployment_id": 42, "filename": "bundle"})
    assert resp.status_code == 404


def test_upload_stores_bundle_and_extracts_manifest(monkeypatch):
    monkeypatch.setattr(diagnostics.clients, "get_deployment", lambda deployment_id, owner_user_id: DEPLOYMENT)
    monkeypatch.setattr(diagnostics.store, "store_bundle", lambda *a, **kw: {"id": 1, **kw})

    with patch.object(diagnostics.clients, "record_snapshot") as mock_snapshot:
        resp = client.post(
            "/api/diagnostics/upload",
            data={"deployment_id": 42, "filename": "bundle"},
            files={
                "logs_file": ("app.log", b"ERROR pool exhausted", "text/plain"),
                "config_file": (
                    "build_manifest.json",
                    b'{"version": "1.4.2", "build_sha": "abc123"}',
                    "application/json",
                ),
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["logs_excerpt"] == "ERROR pool exhausted"
    assert body["extracted_manifest"] == {"version": "1.4.2", "build_sha": "abc123"}
    mock_snapshot.assert_called_once_with(
        42,
        1,
        source="diagnostic_bundle",
        app_version="1.4.2",
        build_sha="abc123",
        manifest={"version": "1.4.2", "build_sha": "abc123"},
    )


def test_upload_without_manifest_does_not_record_snapshot(monkeypatch):
    monkeypatch.setattr(diagnostics.clients, "get_deployment", lambda deployment_id, owner_user_id: DEPLOYMENT)
    monkeypatch.setattr(diagnostics.store, "store_bundle", lambda *a, **kw: {"id": 2, **kw})

    with patch.object(diagnostics.clients, "record_snapshot") as mock_snapshot:
        resp = client.post(
            "/api/diagnostics/upload",
            data={"deployment_id": 42, "filename": "bundle"},
            files={"logs_file": ("app.log", b"just logs, no manifest", "text/plain")},
        )

    assert resp.status_code == 200
    assert resp.json()["extracted_manifest"] is None
    mock_snapshot.assert_not_called()


def test_list_bundles_for_deployment(monkeypatch):
    monkeypatch.setattr(diagnostics.clients, "get_deployment", lambda deployment_id, owner_user_id: DEPLOYMENT)
    monkeypatch.setattr(
        diagnostics.store, "list_bundles",
        lambda deployment_id, owner_user_id: [{"id": 1, "deployment_id": deployment_id}],
    )
    resp = client.get("/api/diagnostics/42")
    assert resp.status_code == 200
    assert resp.json() == [{"id": 1, "deployment_id": 42}]
