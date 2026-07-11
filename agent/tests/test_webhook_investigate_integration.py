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


def test_finishes_partial_when_no_postmortem_produced(monkeypatch):
    finish_mock = _patch_happy_path(monkeypatch, postmortem=None)

    webhooks._investigate_and_report("jira", "OPS-1", "alert", jira_key="OPS-1", owner_user_id=1)

    args = finish_mock.call_args.args
    kwargs = finish_mock.call_args.kwargs
    assert args[1] == "partial"
    assert kwargs["pending_action"] is None
