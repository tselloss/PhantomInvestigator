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


def test_update_investigation_passes_feedback_to_store(monkeypatch):
    captured = {}

    def fake_set_feedback(investigation_id, owner_user_id, reviewed, feedback_rating, feedback_notes):
        captured.update(
            investigation_id=investigation_id, owner_user_id=owner_user_id, reviewed=reviewed,
            feedback_rating=feedback_rating, feedback_notes=feedback_notes,
        )
        return {"id": investigation_id, "reviewed": reviewed}

    monkeypatch.setattr(investigations.store, "set_feedback", fake_set_feedback)
    resp = client.patch(
        "/api/investigations/9",
        json={"reviewed": True, "feedback_rating": "incorrect", "feedback_notes": "wrong root cause"},
    )
    assert resp.status_code == 200
    assert captured == {
        "investigation_id": 9, "owner_user_id": 1, "reviewed": True,
        "feedback_rating": "incorrect", "feedback_notes": "wrong root cause",
    }


def test_update_investigation_rejects_invalid_rating(monkeypatch):
    resp = client.patch("/api/investigations/9", json={"reviewed": True, "feedback_rating": "definitely-wrong"})
    assert resp.status_code == 422


def test_approve_pending_post_calls_jira_and_resolves(monkeypatch):
    item = {"id": 3, "deployment_id": 42, "pending_action": {"type": "jira_comment", "key": "OPS-1", "body": "hi"}}
    monkeypatch.setattr(investigations.store, "get_by_id", lambda investigation_id, owner_user_id: item)
    resolved = {}

    def fake_resolve(investigation_id, owner_user_id):
        resolved.update(investigation_id=investigation_id, owner_user_id=owner_user_id)
        return {"id": investigation_id, "status": "done", "pending_action": None}

    monkeypatch.setattr(investigations.store, "resolve_pending_action", fake_resolve)
    posted = {}
    monkeypatch.setattr(
        investigations.jira, "post_comment",
        lambda key, body, user_id, deployment_id=None: posted.update(key=key, body=body, deployment_id=deployment_id),
    )

    resp = client.post("/api/investigations/3/approve-post")
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
    assert posted == {"key": "OPS-1", "body": "hi", "deployment_id": 42}
    assert resolved == {"investigation_id": 3, "owner_user_id": 1}


def test_approve_pending_post_404_when_no_pending_action(monkeypatch):
    monkeypatch.setattr(investigations.store, "get_by_id", lambda investigation_id, owner_user_id: {"id": 3, "pending_action": None})
    resp = client.post("/api/investigations/3/approve-post")
    assert resp.status_code == 400


def test_dismiss_pending_post_resolves_without_posting(monkeypatch):
    item = {"id": 3, "pending_action": {"type": "jira_comment", "key": "OPS-1", "body": "hi"}}
    monkeypatch.setattr(investigations.store, "get_by_id", lambda investigation_id, owner_user_id: item)
    monkeypatch.setattr(investigations.store, "resolve_pending_action", lambda investigation_id, owner_user_id: {"id": 3, "status": "done"})

    def fail_post_comment(*a, **kw):
        raise AssertionError("dismiss must not post to Jira")

    monkeypatch.setattr(investigations.jira, "post_comment", fail_post_comment)

    resp = client.post("/api/investigations/3/dismiss-post")
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
