"""pending_fix_action is a second, independent pending-write slot alongside
pending_action (see investigations.py's finish()/resolve_pending_action()/
resolve_pending_fix_action()) -- these check the SQL/params each issues
without needing a real Postgres to parse the query against, same convention
as test_investigations_dedup.py."""
import json

import investigations


class _FakeConn:
    def __init__(self, fetchone_result=None):
        self.fetchone_result = fetchone_result
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.queries.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        return self.fetchone_result


def test_resolve_pending_action_only_finishes_if_fix_action_also_clear(monkeypatch):
    fake = _FakeConn(fetchone_result=None)
    monkeypatch.setattr(investigations, "_connect", lambda: fake)

    investigations.resolve_pending_action(3, 1)

    update_query, update_params = fake.queries[0]
    assert "pending_action = NULL" in update_query
    assert "CASE WHEN pending_fix_action IS NULL THEN 'done' ELSE 'awaiting_approval' END" in update_query
    assert update_params == (3, 1)


def test_resolve_pending_fix_action_only_finishes_if_action_also_clear(monkeypatch):
    fake = _FakeConn(fetchone_result=None)
    monkeypatch.setattr(investigations, "_connect", lambda: fake)

    investigations.resolve_pending_fix_action(3, 1)

    update_query, update_params = fake.queries[0]
    assert "pending_fix_action = NULL" in update_query
    assert "CASE WHEN pending_action IS NULL THEN 'done' ELSE 'awaiting_approval' END" in update_query
    assert update_params == (3, 1)


def test_finish_marks_awaiting_approval_when_only_pending_fix_action_given(monkeypatch):
    fake = _FakeConn()
    monkeypatch.setattr(investigations, "_connect", lambda: fake)

    investigations.finish(3, "done", {"x": 1}, pending_fix_action={"type": "github_pr", "repo": "o/r"})

    update_query, update_params = fake.queries[0]
    assert update_params[0] == "awaiting_approval"
    assert update_params[2] is None  # pending_action
    assert json.loads(update_params[3]) == {"type": "github_pr", "repo": "o/r"}


def test_finish_marks_awaiting_approval_when_only_pending_action_given(monkeypatch):
    """Unchanged existing behavior -- pending_fix_action being absent must
    not stop pending_action alone from setting awaiting_approval."""
    fake = _FakeConn()
    monkeypatch.setattr(investigations, "_connect", lambda: fake)

    investigations.finish(3, "done", {"x": 1}, pending_action={"type": "jira_comment", "key": "OPS-1", "body": "hi"})

    update_query, update_params = fake.queries[0]
    assert update_params[0] == "awaiting_approval"
    assert json.loads(update_params[2]) == {"type": "jira_comment", "key": "OPS-1", "body": "hi"}
    assert update_params[3] is None  # pending_fix_action


def test_finish_uses_given_status_when_neither_pending_slot_set(monkeypatch):
    fake = _FakeConn()
    monkeypatch.setattr(investigations, "_connect", lambda: fake)

    investigations.finish(3, "done", {"x": 1})

    update_query, update_params = fake.queries[0]
    assert update_params[0] == "done"
