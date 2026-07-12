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


def test_list_investigations_passes_reviewed_filter(monkeypatch):
    captured = {}

    def fake_list_recent(owner_user_id, **kwargs):
        captured.update(owner_user_id=owner_user_id, **kwargs)
        return []

    monkeypatch.setattr(investigations.store, "list_recent", fake_list_recent)
    resp = client.get("/api/investigations", params={"reviewed": "true"})
    assert resp.status_code == 200
    assert captured["reviewed"] is True


def test_list_investigations_omits_reviewed_when_not_given(monkeypatch):
    captured = {}

    def fake_list_recent(owner_user_id, **kwargs):
        captured.update(owner_user_id=owner_user_id, **kwargs)
        return []

    monkeypatch.setattr(investigations.store, "list_recent", fake_list_recent)
    resp = client.get("/api/investigations")
    assert resp.status_code == 200
    assert captured["reviewed"] is None


def test_get_investigation_includes_jira_url_for_jira_source(monkeypatch):
    item = {"id": 5, "source": "jira", "source_ref": "OPS-9", "deployment_id": 42}
    monkeypatch.setattr(investigations.store, "get_by_id", lambda investigation_id, owner_user_id: dict(item))
    monkeypatch.setattr(
        investigations.jira, "issue_url",
        lambda key, user_id, deployment_id=None: f"https://example.atlassian.net/browse/{key}",
    )

    resp = client.get("/api/investigations/5")
    assert resp.status_code == 200
    assert resp.json()["jira_url"] == "https://example.atlassian.net/browse/OPS-9"


def test_get_investigation_omits_jira_url_for_non_jira_source(monkeypatch):
    item = {"id": 6, "source": "github", "source_ref": "123", "deployment_id": None}
    monkeypatch.setattr(investigations.store, "get_by_id", lambda investigation_id, owner_user_id: dict(item))

    resp = client.get("/api/investigations/6")
    assert resp.status_code == 200
    assert "jira_url" not in resp.json()


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


PENDING_FIX = {
    "type": "github_pr", "repo": "owner/repo", "allowed_base_branches": ["main", "staging"],
    "default_branch": "main", "files": [{"path": "tests/x.py", "content": "new", "diff": "..."}],
    "pr_title": "Fix flaky test", "pr_body": "body",
}
DEPLOYMENT = {"id": 42, "allowed_base_branches": ["main", "staging"]}


def test_approve_pending_fix_opens_pr_and_resolves(monkeypatch):
    item = {"id": 3, "deployment_id": 42, "pending_fix_action": dict(PENDING_FIX)}
    monkeypatch.setattr(investigations.store, "get_by_id", lambda investigation_id, owner_user_id: item)
    monkeypatch.setattr(investigations.clients, "get_deployment", lambda deployment_id, owner_user_id: DEPLOYMENT)
    opened = {}

    def fake_open(repo, target_branch, files, title, body, investigation_id, user_id, deployment_id=None):
        opened.update(
            repo=repo, target_branch=target_branch, files=files, title=title, body=body,
            investigation_id=investigation_id, user_id=user_id, deployment_id=deployment_id,
        )
        return {"ok": True, "pr_url": "https://github.com/owner/repo/pull/9", "branch": "phantom-fix/3"}

    monkeypatch.setattr(investigations.github_actions, "open_fix_pull_request", fake_open)
    resolved = {}
    monkeypatch.setattr(
        investigations.store, "resolve_pending_fix_action",
        lambda investigation_id, owner_user_id: resolved.update(investigation_id=investigation_id, owner_user_id=owner_user_id)
        or {"id": investigation_id, "status": "done", "pending_fix_action": None},
    )

    resp = client.post("/api/investigations/3/approve-fix", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["pr_url"] == "https://github.com/owner/repo/pull/9"
    assert opened["target_branch"] == "main"
    assert opened["repo"] == "owner/repo"
    assert opened["investigation_id"] == 3
    assert opened["deployment_id"] == 42
    assert resolved == {"investigation_id": 3, "owner_user_id": 1}


def test_approve_pending_fix_uses_explicitly_selected_branch(monkeypatch):
    item = {"id": 3, "deployment_id": 42, "pending_fix_action": dict(PENDING_FIX)}
    monkeypatch.setattr(investigations.store, "get_by_id", lambda investigation_id, owner_user_id: item)
    monkeypatch.setattr(investigations.clients, "get_deployment", lambda deployment_id, owner_user_id: DEPLOYMENT)
    opened = {}
    monkeypatch.setattr(
        investigations.github_actions, "open_fix_pull_request",
        lambda repo, target_branch, *a, **kw: opened.update(target_branch=target_branch)
        or {"ok": True, "pr_url": "https://x", "branch": "phantom-fix/3"},
    )
    monkeypatch.setattr(investigations.store, "resolve_pending_fix_action", lambda investigation_id, owner_user_id: {"id": 3, "status": "done"})

    resp = client.post("/api/investigations/3/approve-fix", json={"target_branch": "staging"})
    assert resp.status_code == 200
    assert opened["target_branch"] == "staging"


def test_approve_pending_fix_rejects_branch_not_in_live_allowlist(monkeypatch):
    """The allowlist is re-checked against the deployment's CURRENT config,
    not the snapshot captured in pending_fix_action -- an operator may have
    edited it since the proposal was built."""
    item = {"id": 3, "deployment_id": 42, "pending_fix_action": dict(PENDING_FIX)}
    monkeypatch.setattr(investigations.store, "get_by_id", lambda investigation_id, owner_user_id: item)
    monkeypatch.setattr(investigations.clients, "get_deployment", lambda deployment_id, owner_user_id: {"id": 42, "allowed_base_branches": ["main"]})

    def fail_open(*a, **kw):
        raise AssertionError("must not open a PR against a branch outside the live allowlist")

    monkeypatch.setattr(investigations.github_actions, "open_fix_pull_request", fail_open)

    resp = client.post("/api/investigations/3/approve-fix", json={"target_branch": "staging"})
    assert resp.status_code == 400


def test_approve_pending_fix_400_when_no_pending_fix_action(monkeypatch):
    monkeypatch.setattr(investigations.store, "get_by_id", lambda investigation_id, owner_user_id: {"id": 3, "pending_fix_action": None})
    resp = client.post("/api/investigations/3/approve-fix", json={})
    assert resp.status_code == 400


def test_approve_pending_fix_502_when_open_fails(monkeypatch):
    item = {"id": 3, "deployment_id": 42, "pending_fix_action": dict(PENDING_FIX)}
    monkeypatch.setattr(investigations.store, "get_by_id", lambda investigation_id, owner_user_id: item)
    monkeypatch.setattr(investigations.clients, "get_deployment", lambda deployment_id, owner_user_id: DEPLOYMENT)
    monkeypatch.setattr(
        investigations.github_actions, "open_fix_pull_request",
        lambda *a, **kw: {"ok": False, "error": "branch already exists"},
    )
    resp = client.post("/api/investigations/3/approve-fix", json={})
    assert resp.status_code == 502


def test_dismiss_pending_fix_resolves_without_opening_pr(monkeypatch):
    item = {"id": 3, "pending_fix_action": dict(PENDING_FIX)}
    monkeypatch.setattr(investigations.store, "get_by_id", lambda investigation_id, owner_user_id: item)
    monkeypatch.setattr(investigations.store, "resolve_pending_fix_action", lambda investigation_id, owner_user_id: {"id": 3, "status": "done"})

    def fail_open(*a, **kw):
        raise AssertionError("dismiss must not open a PR")

    monkeypatch.setattr(investigations.github_actions, "open_fix_pull_request", fail_open)

    resp = client.post("/api/investigations/3/dismiss-fix")
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


def test_dismiss_pending_fix_400_when_no_pending_fix_action(monkeypatch):
    monkeypatch.setattr(investigations.store, "get_by_id", lambda investigation_id, owner_user_id: {"id": 3, "pending_fix_action": None})
    resp = client.post("/api/investigations/3/dismiss-fix")
    assert resp.status_code == 400
