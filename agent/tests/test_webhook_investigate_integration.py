"""_investigate_and_report is the function webhooks.py's background task
actually runs; test_webhooks.py mocks it out entirely to test the HTTP
layer. These tests cover its own orchestration -- dedup/budget short
circuits, and what gets passed to investigations.finish() -- since each
piece (find_recent_duplicate, check_budget) already has its own unit tests
elsewhere but nothing exercised them wired together."""
from unittest.mock import MagicMock

from routes import webhooks


def _patch_happy_path(monkeypatch, postmortem=None):
    monkeypatch.setattr(webhooks.investigations, "find_recent_duplicate", lambda *a, **k: None)
    monkeypatch.setattr(webhooks.billing, "check_budget", lambda owner_user_id: {"allowed": True})
    monkeypatch.setattr(webhooks.investigations, "start", lambda *a, **k: 123)
    monkeypatch.setattr(webhooks.clients, "build_loop_alert_text", lambda alert_text, *a, **k: alert_text)
    monkeypatch.setattr(webhooks, "run_agent", lambda *a, **k: {"postmortem": postmortem} if postmortem else {})
    finish_mock = MagicMock()
    monkeypatch.setattr(webhooks.investigations, "finish", finish_mock)
    return finish_mock


def test_skips_entirely_when_owner_unresolved(monkeypatch):
    dedup_mock = MagicMock()
    monkeypatch.setattr(webhooks.investigations, "find_recent_duplicate", dedup_mock)

    webhooks._investigate_and_report("jira", "OPS-1", "alert", owner_user_id=None)

    dedup_mock.assert_not_called()


def test_skips_on_recent_duplicate(monkeypatch):
    monkeypatch.setattr(webhooks.investigations, "find_recent_duplicate", lambda *a, **k: {"id": 5})
    budget_mock = MagicMock()
    monkeypatch.setattr(webhooks.billing, "check_budget", budget_mock)
    start_mock = MagicMock()
    monkeypatch.setattr(webhooks.investigations, "start", start_mock)

    webhooks._investigate_and_report("jira", "OPS-1", "alert", owner_user_id=1)

    budget_mock.assert_not_called()
    start_mock.assert_not_called()


def test_skips_when_budget_exceeded(monkeypatch):
    monkeypatch.setattr(webhooks.investigations, "find_recent_duplicate", lambda *a, **k: None)
    monkeypatch.setattr(webhooks.billing, "check_budget", lambda owner_user_id: {"allowed": False, "spent_usd": 5, "limit_usd": 5})
    start_mock = MagicMock()
    monkeypatch.setattr(webhooks.investigations, "start", start_mock)

    webhooks._investigate_and_report("jira", "OPS-1", "alert", owner_user_id=1)

    start_mock.assert_not_called()


def test_runs_and_queues_pending_jira_comment_when_postmortem_produced(monkeypatch):
    postmortem = {"title": "DB pool exhausted", "confidence": 0.8, "root_cause": "leak", "suggested_fix": "cap pool"}
    finish_mock = _patch_happy_path(monkeypatch, postmortem=postmortem)

    webhooks._investigate_and_report("jira", "OPS-1", "alert", jira_key="OPS-1", owner_user_id=1)

    finish_mock.assert_called_once()
    investigation_id, status, result, kwargs = finish_mock.call_args.args[0], finish_mock.call_args.args[1], finish_mock.call_args.args[2], finish_mock.call_args.kwargs
    assert investigation_id == 123
    assert status == "done"
    assert kwargs["pending_action"]["type"] == "jira_comment"
    assert kwargs["pending_action"]["key"] == "OPS-1"
    assert "DB pool exhausted" in kwargs["pending_action"]["body"]


def test_no_pending_action_without_jira_key(monkeypatch):
    postmortem = {"title": "x", "confidence": 0.5, "root_cause": "y", "suggested_fix": "z"}
    finish_mock = _patch_happy_path(monkeypatch, postmortem=postmortem)

    webhooks._investigate_and_report("github", "99", "alert", jira_key=None, owner_user_id=1)

    kwargs = finish_mock.call_args.kwargs
    assert kwargs["pending_action"] is None


def test_runs_and_queues_pending_azure_devops_comment_when_postmortem_produced(monkeypatch):
    postmortem = {"title": "orders-api 502s", "confidence": 0.9, "root_cause": "timeout too low", "suggested_fix": "revert"}
    finish_mock = _patch_happy_path(monkeypatch, postmortem=postmortem)

    webhooks._investigate_and_report("azure_devops", "42", "alert", owner_user_id=1, azure_devops_work_item_id=42)

    finish_mock.assert_called_once()
    kwargs = finish_mock.call_args.kwargs
    assert kwargs["pending_action"]["type"] == "azure_devops_comment"
    assert kwargs["pending_action"]["work_item_id"] == 42
    assert "orders-api 502s" in kwargs["pending_action"]["body"]


def test_jira_key_takes_precedence_over_azure_devops_work_item_id(monkeypatch):
    """Only one of these should ever be set by a real caller (each webhook
    handler passes exactly one), but if both were somehow present, Jira
    winning is an arbitrary-but-deterministic choice, not a real requirement."""
    postmortem = {"title": "x", "confidence": 0.5, "root_cause": "y", "suggested_fix": "z"}
    finish_mock = _patch_happy_path(monkeypatch, postmortem=postmortem)

    webhooks._investigate_and_report(
        "jira", "OPS-1", "alert", jira_key="OPS-1", owner_user_id=1, azure_devops_work_item_id=42
    )

    kwargs = finish_mock.call_args.kwargs
    assert kwargs["pending_action"]["type"] == "jira_comment"


def test_finishes_partial_when_no_postmortem_produced(monkeypatch):
    finish_mock = _patch_happy_path(monkeypatch, postmortem=None)

    webhooks._investigate_and_report("jira", "OPS-1", "alert", jira_key="OPS-1", owner_user_id=1)

    args = finish_mock.call_args.args
    kwargs = finish_mock.call_args.kwargs
    assert args[1] == "partial"
    assert kwargs["pending_action"] is None
    assert kwargs["pending_fix_action"] is None


def test_no_pending_fix_action_without_deployment_id(monkeypatch):
    """No deployment_id means no deployment to look up -- clients.get_deployment
    must not even be called (it isn't mocked here, so a call would hit a real
    DB and fail the test), and pending_fix_action stays None."""
    postmortem = {"title": "x", "confidence": 0.5, "root_cause": "y", "suggested_fix": "z"}
    finish_mock = _patch_happy_path(monkeypatch, postmortem=postmortem)

    webhooks._investigate_and_report("jira", "OPS-1", "alert", jira_key="OPS-1", owner_user_id=1)

    assert finish_mock.call_args.kwargs["pending_fix_action"] is None


def test_queues_pending_fix_action_when_build_pending_fix_action_returns_one(monkeypatch):
    postmortem = {
        "title": "Flaky checkout test", "confidence": 0.8, "root_cause": "missing wait",
        "suggested_fix": "add wait", "proposed_fix_files": [{"path": "tests/x.spec.js", "content": "new"}],
    }
    finish_mock = _patch_happy_path(monkeypatch, postmortem=postmortem)
    deployment = {"id": 42, "github_repo": "owner/repo", "allowed_base_branches": ["main"]}
    monkeypatch.setattr(webhooks.clients, "get_deployment", lambda deployment_id, owner_user_id: deployment)
    fake_pending_fix = {"type": "github_pr", "repo": "owner/repo"}
    build_mock = MagicMock(return_value=fake_pending_fix)
    monkeypatch.setattr(webhooks.fix_proposals, "build_pending_fix_action", build_mock)

    webhooks._investigate_and_report("jira", "OPS-1", "alert", jira_key="OPS-1", deployment_id=42, owner_user_id=1)

    assert finish_mock.call_args.kwargs["pending_fix_action"] == fake_pending_fix
    build_mock.assert_called_once_with(postmortem, deployment, [], 1)
