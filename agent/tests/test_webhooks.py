import hashlib
import hmac
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from routes import webhooks

client = TestClient(main.app)


def _no_deployment(*_args, **_kwargs):
    return None


def test_jira_webhook_rejects_bad_secret(monkeypatch):
    monkeypatch.setattr(webhooks, "JIRA_WEBHOOK_SECRET", "s3cr3t")
    resp = client.post("/webhooks/jira?secret=wrong", json={"issue": {"key": "OPS-1", "fields": {"summary": "x"}}})
    assert resp.status_code == 401


def test_jira_webhook_rejects_when_secret_not_configured(monkeypatch):
    monkeypatch.setattr(webhooks, "JIRA_WEBHOOK_SECRET", "")
    resp = client.post("/webhooks/jira?secret=anything", json={"issue": {"key": "OPS-1", "fields": {}}})
    assert resp.status_code == 401


def test_jira_webhook_requires_issue_key(monkeypatch):
    monkeypatch.setattr(webhooks, "JIRA_WEBHOOK_SECRET", "s3cr3t")
    resp = client.post("/webhooks/jira?secret=s3cr3t", json={"issue": {}})
    assert resp.status_code == 400


def test_jira_webhook_accepts_valid_secret_and_schedules_investigation(monkeypatch):
    monkeypatch.setattr(webhooks, "JIRA_WEBHOOK_SECRET", "s3cr3t")
    with patch.object(webhooks, "_investigate_and_report") as mock_investigate:
        resp = client.post(
            "/webhooks/jira?secret=s3cr3t",
            json={"issue": {"key": "OPS-1", "fields": {"summary": "checkout down"}}},
        )

    assert resp.status_code == 200
    assert resp.json() == {"accepted": True, "key": "OPS-1"}
    mock_investigate.assert_called_once()
    source, source_ref, alert_text, jira_key, deployment_id, owner_user_id = mock_investigate.call_args.args
    assert source == "jira"
    assert source_ref == "OPS-1"
    assert "checkout down" in alert_text
    assert jira_key == "OPS-1"
    assert deployment_id is None  # payload has no project key, so nothing to resolve
    assert owner_user_id is None


def test_jira_webhook_resolves_known_deployment(monkeypatch):
    monkeypatch.setattr(webhooks, "JIRA_WEBHOOK_SECRET", "s3cr3t")
    monkeypatch.setattr(
        webhooks.clients, "find_deployment_by_jira_project",
        lambda key: {"id": 42, "client_id": 7, "owner_user_id": 1, "label": "prod"} if key == "OPS" else None,
    )
    monkeypatch.setattr(webhooks.clients, "get_client", lambda client_id, owner_user_id: {"id": 7, "name": "Acme Corp"})

    with patch.object(webhooks, "_investigate_and_report") as mock_investigate:
        resp = client.post(
            "/webhooks/jira?secret=s3cr3t",
            json={"issue": {"key": "OPS-1", "fields": {"summary": "checkout down", "project": {"key": "OPS"}}}},
        )

    assert resp.status_code == 200
    _, _, alert_text, _, deployment_id, owner_user_id = mock_investigate.call_args.args
    assert deployment_id == 42
    assert owner_user_id == 1
    assert "Acme Corp / prod (id 42)" in alert_text


def _github_signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_github_webhook_rejects_bad_signature(monkeypatch):
    monkeypatch.setattr(webhooks, "GITHUB_WEBHOOK_SECRET", "ghsecret")
    body = json.dumps({"workflow_run": {"conclusion": "failure"}}).encode()
    resp = client.post(
        "/webhooks/github",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=deadbeef", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


def test_github_webhook_rejects_when_secret_not_configured(monkeypatch):
    monkeypatch.setattr(webhooks, "GITHUB_WEBHOOK_SECRET", "")
    body = json.dumps({"workflow_run": {"conclusion": "failure"}}).encode()
    resp = client.post(
        "/webhooks/github",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=whatever", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


def test_github_webhook_accepts_valid_signature_and_schedules_on_failure(monkeypatch):
    monkeypatch.setattr(webhooks, "GITHUB_WEBHOOK_SECRET", "ghsecret")
    monkeypatch.setattr(webhooks.clients, "find_deployment_by_github_repo", _no_deployment)
    payload = {
        "workflow_run": {
            "id": 99,
            "name": "CI",
            "conclusion": "failure",
            "head_branch": "main",
            "head_sha": "abcdef1234",
        },
        "repository": {"full_name": "owner/repo"},
    }
    body = json.dumps(payload).encode()
    sig = _github_signature("ghsecret", body)

    with patch.object(webhooks, "_investigate_and_report") as mock_investigate:
        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"accepted": True, "run_id": 99}
    mock_investigate.assert_called_once()
    source, source_ref, alert_text, jira_key, deployment_id, owner_user_id = mock_investigate.call_args.args
    assert source == "github"
    assert source_ref == "99"
    assert "owner/repo" in alert_text
    assert jira_key is None
    assert deployment_id is None
    assert owner_user_id is None


def test_github_webhook_ignores_non_failure_conclusion(monkeypatch):
    monkeypatch.setattr(webhooks, "GITHUB_WEBHOOK_SECRET", "ghsecret")
    payload = {"workflow_run": {"id": 1, "conclusion": "success"}, "repository": {"full_name": "owner/repo"}}
    body = json.dumps(payload).encode()
    sig = _github_signature("ghsecret", body)

    with patch.object(webhooks, "_investigate_and_report") as mock_investigate:
        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"accepted": False, "reason": "not a failed run"}
    mock_investigate.assert_not_called()


def _ado_payload(event_type="workitem.created", work_item_type="Bug", **resource_overrides):
    resource = {
        "id": 42,
        "workItemId": 42,
        "url": "https://dev.azure.com/contoso/_apis/wit/workItems/42",
        "fields": {
            "System.Title": "Checkout down",
            "System.WorkItemType": work_item_type,
            "System.TeamProject": "MyProject",
        },
        **resource_overrides,
    }
    return {"eventType": event_type, "resource": resource}


def test_azure_devops_webhook_rejects_bad_secret(monkeypatch):
    monkeypatch.setattr(webhooks, "AZURE_DEVOPS_WEBHOOK_SECRET", "s3cr3t")
    resp = client.post("/webhooks/azure_devops?secret=wrong", json=_ado_payload())
    assert resp.status_code == 401


def test_azure_devops_webhook_rejects_when_secret_not_configured(monkeypatch):
    monkeypatch.setattr(webhooks, "AZURE_DEVOPS_WEBHOOK_SECRET", "")
    resp = client.post("/webhooks/azure_devops?secret=anything", json=_ado_payload())
    assert resp.status_code == 401


def test_azure_devops_webhook_ignores_unrelated_event_type(monkeypatch):
    monkeypatch.setattr(webhooks, "AZURE_DEVOPS_WEBHOOK_SECRET", "s3cr3t")
    with patch.object(webhooks, "_investigate_and_report") as mock_investigate:
        resp = client.post(
            "/webhooks/azure_devops?secret=s3cr3t", json=_ado_payload(event_type="workitem.commented")
        )
    assert resp.status_code == 200
    assert resp.json() == {"accepted": False, "reason": "ignoring event type 'workitem.commented'"}
    mock_investigate.assert_not_called()


def test_azure_devops_webhook_ignores_non_bug_work_item_types(monkeypatch):
    monkeypatch.setattr(webhooks, "AZURE_DEVOPS_WEBHOOK_SECRET", "s3cr3t")
    with patch.object(webhooks, "_investigate_and_report") as mock_investigate:
        resp = client.post(
            "/webhooks/azure_devops?secret=s3cr3t", json=_ado_payload(work_item_type="Task")
        )
    assert resp.status_code == 200
    assert resp.json() == {"accepted": False, "reason": "ignoring work item type 'Task'"}
    mock_investigate.assert_not_called()


def test_azure_devops_webhook_accepts_valid_secret_and_schedules_investigation(monkeypatch):
    monkeypatch.setattr(webhooks, "AZURE_DEVOPS_WEBHOOK_SECRET", "s3cr3t")
    monkeypatch.setattr(webhooks.clients, "find_deployment_by_azure_devops_project", _no_deployment)
    with patch.object(webhooks, "_investigate_and_report") as mock_investigate:
        resp = client.post("/webhooks/azure_devops?secret=s3cr3t", json=_ado_payload())

    assert resp.status_code == 200
    assert resp.json() == {"accepted": True, "work_item_id": 42}
    mock_investigate.assert_called_once()
    args, kwargs = mock_investigate.call_args.args, mock_investigate.call_args.kwargs
    source, source_ref, alert_text, jira_key, deployment_id, owner_user_id = args
    assert source == "azure_devops"
    assert source_ref == "42"
    assert "Checkout down" in alert_text
    assert jira_key is None
    assert deployment_id is None
    assert owner_user_id is None
    assert kwargs["azure_devops_work_item_id"] == 42


def test_azure_devops_webhook_reads_full_snapshot_from_revision_on_update(monkeypatch):
    """Real captured payload shape: workitem.updated's top-level
    resource.fields is a {oldValue, newValue} diff of only what changed (a
    State-only change has no Title/WorkItemType/TeamProject in it at all) --
    the full current snapshot lives under resource.revision.fields instead."""
    monkeypatch.setattr(webhooks, "AZURE_DEVOPS_WEBHOOK_SECRET", "s3cr3t")
    monkeypatch.setattr(webhooks.clients, "find_deployment_by_azure_devops_project", _no_deployment)
    payload = {
        "eventType": "workitem.updated",
        "resource": {
            "id": 6,
            "workItemId": 6,
            "url": "https://dev.azure.com/contoso/f0d3d2dc/_apis/wit/workItems/6",
            "fields": {"System.State": {"oldValue": "To Do", "newValue": "Doing"}},
            "revision": {
                "fields": {
                    "System.Title": "Checkout down",
                    "System.WorkItemType": "Bug",
                    "System.TeamProject": "MyProject",
                    "System.State": "Doing",
                }
            },
        },
    }
    with patch.object(webhooks, "_investigate_and_report") as mock_investigate:
        resp = client.post("/webhooks/azure_devops?secret=s3cr3t", json=payload)

    assert resp.status_code == 200
    assert resp.json() == {"accepted": True, "work_item_id": 6}
    mock_investigate.assert_called_once()
    _, source_ref, alert_text, *_ = mock_investigate.call_args.args
    assert source_ref == "6"
    assert "Checkout down" in alert_text


def test_azure_devops_webhook_resolves_known_deployment(monkeypatch):
    monkeypatch.setattr(webhooks, "AZURE_DEVOPS_WEBHOOK_SECRET", "s3cr3t")
    monkeypatch.setattr(
        webhooks.clients, "find_deployment_by_azure_devops_project",
        lambda key: {"id": 8, "client_id": 11, "owner_user_id": 4, "label": "production"}
        if key == "contoso/MyProject" else None,
    )
    monkeypatch.setattr(webhooks.clients, "get_client", lambda client_id, owner_user_id: {"id": 11, "name": "Northwind"})

    with patch.object(webhooks, "_investigate_and_report") as mock_investigate:
        resp = client.post("/webhooks/azure_devops?secret=s3cr3t", json=_ado_payload())

    assert resp.status_code == 200
    args, kwargs = mock_investigate.call_args.args, mock_investigate.call_args.kwargs
    _, _, alert_text, _, deployment_id, owner_user_id = args
    assert deployment_id == 8
    assert owner_user_id == 4
    assert "Northwind / production (id 8)" in alert_text
    assert kwargs["azure_devops_work_item_id"] == 42
