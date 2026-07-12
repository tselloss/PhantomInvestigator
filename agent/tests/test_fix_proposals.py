import fix_proposals

DEPLOYMENT = {
    "id": 42, "github_repo": "owner/repo", "allowed_base_branches": ["main", "staging"],
}

PM = {
    "title": "Flaky checkout test",
    "confidence": 0.8,
    "root_cause": "Missing explicit wait before assertion.",
    "suggested_fix": "Add waitForElement before the assertion.",
    "proposed_fix_files": [{"path": "tests/checkout_flow.spec.js", "content": "new content"}],
}


def test_no_proposal_without_postmortem():
    assert fix_proposals.build_pending_fix_action(None, DEPLOYMENT, ["tests/checkout_flow.spec.js"], 1) is None


def test_no_proposal_without_proposed_fix_files():
    pm = {**PM, "proposed_fix_files": None}
    assert fix_proposals.build_pending_fix_action(pm, DEPLOYMENT, [], 1) is None


def test_no_proposal_without_deployment():
    assert fix_proposals.build_pending_fix_action(PM, None, ["tests/checkout_flow.spec.js"], 1) is None


def test_no_proposal_without_github_repo():
    deployment = {**DEPLOYMENT, "github_repo": None}
    assert fix_proposals.build_pending_fix_action(PM, deployment, ["tests/checkout_flow.spec.js"], 1) is None


def test_no_proposal_without_allowed_base_branches():
    deployment = {**DEPLOYMENT, "allowed_base_branches": None}
    assert fix_proposals.build_pending_fix_action(PM, deployment, ["tests/checkout_flow.spec.js"], 1) is None
    deployment = {**DEPLOYMENT, "allowed_base_branches": []}
    assert fix_proposals.build_pending_fix_action(PM, deployment, ["tests/checkout_flow.spec.js"], 1) is None


def test_whole_proposal_dropped_when_a_file_was_not_read(monkeypatch):
    called = []
    monkeypatch.setattr(fix_proposals.github_actions, "get_file_contents", lambda *a, **k: called.append(1) or "old content")
    assert fix_proposals.build_pending_fix_action(PM, DEPLOYMENT, [], 1) is None
    assert not called  # never even tries to fetch/diff -- rejected before that


def test_whole_proposal_dropped_when_only_some_files_were_read(monkeypatch):
    pm = {
        **PM,
        "proposed_fix_files": [
            {"path": "tests/checkout_flow.spec.js", "content": "new"},
            {"path": "tests/other.spec.js", "content": "new2"},
        ],
    }
    monkeypatch.setattr(fix_proposals.github_actions, "get_file_contents", lambda *a, **k: "old content")
    assert fix_proposals.build_pending_fix_action(pm, DEPLOYMENT, ["tests/checkout_flow.spec.js"], 1) is None


def test_whole_proposal_dropped_when_current_content_unreadable(monkeypatch):
    monkeypatch.setattr(fix_proposals.github_actions, "get_file_contents", lambda *a, **k: "ERROR: not found")
    assert fix_proposals.build_pending_fix_action(PM, DEPLOYMENT, ["tests/checkout_flow.spec.js"], 1) is None


def test_successful_proposal_shape(monkeypatch):
    captured = {}

    def fake_get_file_contents(repo, path, ref, user_id, deployment_id=None):
        captured.update(repo=repo, path=path, ref=ref, user_id=user_id, deployment_id=deployment_id)
        return "old content\n"

    monkeypatch.setattr(fix_proposals.github_actions, "get_file_contents", fake_get_file_contents)
    result = fix_proposals.build_pending_fix_action(PM, DEPLOYMENT, ["tests/checkout_flow.spec.js"], 1)

    assert result["type"] == "github_pr"
    assert result["repo"] == "owner/repo"
    assert result["allowed_base_branches"] == ["main", "staging"]
    assert result["default_branch"] == "main"
    assert len(result["files"]) == 1
    assert result["files"][0]["path"] == "tests/checkout_flow.spec.js"
    assert result["files"][0]["content"] == "new content"
    assert "-old content" in result["files"][0]["diff"]
    assert "+new content" in result["files"][0]["diff"]
    assert "Flaky checkout test" in result["pr_title"]
    assert "80% confidence" in result["pr_body"]

    # fetched the CURRENT content against the deployment's first allowed
    # branch, on behalf of the right user/deployment -- never reused from
    # anything cached at investigation time.
    assert captured == {
        "repo": "owner/repo", "path": "tests/checkout_flow.spec.js", "ref": "main",
        "user_id": 1, "deployment_id": 42,
    }
