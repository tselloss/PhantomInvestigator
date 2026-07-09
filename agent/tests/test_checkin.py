from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from routes import checkin

client = TestClient(main.app)

DEPLOYMENT = {"id": 42, "client_id": 7, "owner_user_id": 1, "label": "prod", "checkin_token": "s3cr3t-token"}


def test_checkin_rejects_unknown_deployment(monkeypatch):
    monkeypatch.setattr(checkin.clients, "get_deployment_unscoped", lambda deployment_id: None)
    resp = client.post("/webhooks/checkin/42?secret=whatever", json={"version": "1.0.0"})
    assert resp.status_code == 401


def test_checkin_rejects_wrong_token(monkeypatch):
    monkeypatch.setattr(checkin.clients, "get_deployment_unscoped", lambda deployment_id: DEPLOYMENT)
    resp = client.post("/webhooks/checkin/42?secret=wrong-token", json={"version": "1.0.0"})
    assert resp.status_code == 401


def test_checkin_rejects_when_deployment_has_no_token(monkeypatch):
    monkeypatch.setattr(
        checkin.clients, "get_deployment_unscoped", lambda deployment_id: {**DEPLOYMENT, "checkin_token": None}
    )
    resp = client.post("/webhooks/checkin/42?secret=", json={"version": "1.0.0"})
    assert resp.status_code == 401


def test_checkin_accepts_valid_token_and_records_snapshot(monkeypatch):
    monkeypatch.setattr(checkin.clients, "get_deployment_unscoped", lambda deployment_id: DEPLOYMENT)
    with patch.object(checkin.clients, "record_snapshot", return_value={"id": 99}) as mock_record:
        resp = client.post(
            "/webhooks/checkin/42?secret=s3cr3t-token",
            json={"version": "1.4.2", "build_sha": "abc123", "applied_patch_ids": ["hotfix-7"]},
        )

    assert resp.status_code == 200
    assert resp.json() == {"accepted": True, "snapshot_id": 99}
    mock_record.assert_called_once()
    args, kwargs = mock_record.call_args
    assert args[0] == 42
    assert args[1] == 1  # owner_user_id, from the resolved deployment's own owner
    assert kwargs["source"] == "self_report"
    assert kwargs["app_version"] == "1.4.2"
    assert kwargs["build_sha"] == "abc123"
    assert kwargs["manifest"]["applied_patch_ids"] == ["hotfix-7"]
