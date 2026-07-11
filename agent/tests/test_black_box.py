from unittest.mock import patch

import pytest

import clients
from routes import webhooks


@pytest.fixture(autouse=True)
def budget_ok(monkeypatch):
    """_investigate_and_report now checks billing.check_budget before
    starting a run -- default it to always-allowed so the many tests below
    that aren't about budgeting don't need to know about it (real
    check_budget would hit a live DB, which isn't available in these unit
    tests). Budget-specific tests override this."""
    monkeypatch.setattr(webhooks.billing, "check_budget", lambda user_id: {"allowed": True, "spent_usd": 0.0, "limit_usd": None})


def test_build_loop_alert_text_no_deployment():
    assert clients.build_loop_alert_text("plain alert", 1, None, 1) == "plain alert"


def test_build_loop_alert_text_known_deployment_no_black_box_note():
    with patch.object(clients, "is_black_box", return_value=False):
        text = clients.build_loop_alert_text("checkout down", 7, 42, 1)
    assert text == "Investigation id: 7. checkout down"
    assert "UNKNOWN" not in text


def test_build_loop_alert_text_black_box_appends_note():
    with patch.object(clients, "is_black_box", return_value=True):
        text = clients.build_loop_alert_text("checkout down", 7, 42, 1)
    assert text.startswith("Investigation id: 7. checkout down")
    assert "UNKNOWN" in text
    assert "record_version_fingerprint" in text


def test_is_black_box_true_when_no_snapshot():
    with patch.object(clients, "get_latest_snapshot", return_value=None):
        assert clients.is_black_box(42, 1) is True


def test_is_black_box_false_when_snapshot_exists():
    with patch.object(clients, "get_latest_snapshot", return_value={"id": 1}):
        assert clients.is_black_box(42, 1) is False


def test_is_black_box_false_without_deployment():
    assert clients.is_black_box(None, 1) is False


def test_investigate_and_report_folds_black_box_note_into_loop_alert_text(monkeypatch):
    monkeypatch.setattr(webhooks.investigations, "find_recent_duplicate", lambda *a, **kw: None)
    monkeypatch.setattr(webhooks.investigations, "start", lambda *a, **kw: 7)
    monkeypatch.setattr(webhooks.investigations, "finish", lambda *a, **kw: None)
    monkeypatch.setattr(webhooks.clients, "is_black_box", lambda deployment_id, owner_user_id: True)

    with patch.object(webhooks, "run_agent", return_value={"postmortem": None}) as mock_run:
        webhooks._investigate_and_report("jira", "OPS-1", "checkout down", "OPS-1", deployment_id=42, owner_user_id=1)

    mock_run.assert_called_once()
    called_alert = mock_run.call_args.args[0]
    assert "Investigation id: 7" in called_alert
    assert "checkout down" in called_alert
    assert "UNKNOWN" in called_alert


def test_investigate_and_report_skips_run_agent_when_duplicate_found(monkeypatch):
    existing = {"id": 5, "result": {"postmortem": None}}
    monkeypatch.setattr(webhooks.investigations, "find_recent_duplicate", lambda *a, **kw: existing)
    monkeypatch.setattr(
        webhooks.investigations, "start",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not start a new investigation")),
    )

    with patch.object(webhooks, "run_agent") as mock_run:
        webhooks._investigate_and_report("jira", "OPS-1", "checkout down", "OPS-1", deployment_id=42, owner_user_id=1)

    mock_run.assert_not_called()


def test_investigate_and_report_skips_run_agent_when_budget_exceeded(monkeypatch):
    monkeypatch.setattr(webhooks.investigations, "find_recent_duplicate", lambda *a, **kw: None)
    monkeypatch.setattr(webhooks.billing, "check_budget", lambda user_id: {"allowed": False, "spent_usd": 10.0, "limit_usd": 10.0})
    monkeypatch.setattr(
        webhooks.investigations, "start",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not start a new investigation")),
    )

    with patch.object(webhooks, "run_agent") as mock_run:
        webhooks._investigate_and_report("jira", "OPS-1", "checkout down", "OPS-1", deployment_id=42, owner_user_id=1)

    mock_run.assert_not_called()


def test_investigate_and_report_proceeds_when_budget_ok(monkeypatch):
    monkeypatch.setattr(webhooks.investigations, "find_recent_duplicate", lambda *a, **kw: None)
    monkeypatch.setattr(webhooks.billing, "check_budget", lambda user_id: {"allowed": True, "spent_usd": 1.0, "limit_usd": 10.0})
    monkeypatch.setattr(webhooks.investigations, "start", lambda *a, **kw: 8)
    monkeypatch.setattr(webhooks.investigations, "finish", lambda *a, **kw: None)

    with patch.object(webhooks, "run_agent", return_value={"postmortem": None}) as mock_run:
        webhooks._investigate_and_report("jira", "OPS-1", "checkout down", "OPS-1", deployment_id=42, owner_user_id=1)

    mock_run.assert_called_once()


def test_investigate_and_report_skips_entirely_when_no_owner_resolved(monkeypatch):
    """An unresolved deployment (webhook's project/repo doesn't match any
    registered deployment) has no owner to attribute the investigation to
    and no correct AI key/credentials to run it under -- must not create an
    ownerless investigation or spend any tokens."""
    monkeypatch.setattr(
        webhooks.investigations, "start",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not start a new investigation")),
    )

    with patch.object(webhooks, "run_agent") as mock_run:
        webhooks._investigate_and_report("jira", "OPS-1", "checkout down", "OPS-1", deployment_id=None, owner_user_id=None)

    mock_run.assert_not_called()


def test_deployment_note_known_deployment():
    deployment = {"id": 42, "client_id": 7, "label": "prod"}
    with (
        patch.object(clients, "get_deployment", return_value=deployment),
        patch.object(clients, "get_client", return_value={"id": 7, "name": "Acme Corp"}),
    ):
        note = clients.deployment_note(42, 1)
    assert note == "Deployment: Acme Corp / prod (id 42). "


def test_deployment_note_no_deployment_id():
    assert clients.deployment_note(None, 1) == ""


def test_deployment_note_unknown_deployment():
    with patch.object(clients, "get_deployment", return_value=None):
        assert clients.deployment_note(42, 1) == ""


def test_investigate_and_report_no_note_without_deployment(monkeypatch):
    monkeypatch.setattr(webhooks.investigations, "find_recent_duplicate", lambda *a, **kw: None)
    monkeypatch.setattr(webhooks.investigations, "start", lambda *a, **kw: 9)
    monkeypatch.setattr(webhooks.investigations, "finish", lambda *a, **kw: None)

    with patch.object(webhooks, "run_agent", return_value={"postmortem": None}) as mock_run:
        webhooks._investigate_and_report("github", "99", "run failed", deployment_id=None, owner_user_id=1)

    mock_run.assert_called_once_with("run failed", 1, deployment_id=None)


def test_investigate_and_report_queues_pending_jira_post_instead_of_posting(monkeypatch):
    """A webhook-triggered Jira post is a high-stakes external write, so it
    must be queued as a pending_action for operator approval (see
    routes/investigations.py's approve-post) rather than fired immediately."""
    monkeypatch.setattr(webhooks.investigations, "find_recent_duplicate", lambda *a, **kw: None)
    monkeypatch.setattr(webhooks.investigations, "start", lambda *a, **kw: 7)
    finish_calls = []
    monkeypatch.setattr(webhooks.investigations, "finish", lambda *a, **kw: finish_calls.append((a, kw)))
    monkeypatch.setattr(webhooks.clients, "is_black_box", lambda deployment_id, owner_user_id: False)
    postmortem = {"title": "Pool exhaustion", "confidence": 0.8, "root_cause": "x", "suggested_fix": "y"}

    with patch.object(webhooks, "run_agent", return_value={"postmortem": postmortem}):
        webhooks._investigate_and_report("jira", "OPS-1", "checkout down", "OPS-1", deployment_id=42, owner_user_id=1)

    assert len(finish_calls) == 1
    args, kwargs = finish_calls[0]
    pending_action = kwargs.get("pending_action") if "pending_action" in kwargs else args[3]
    assert pending_action["type"] == "jira_comment"
    assert pending_action["key"] == "OPS-1"
    assert "Pool exhaustion" in pending_action["body"]
