import base64

import httpx
import respx

from tools import github_actions as ga


def test_get_recent_runs_requires_token(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "")
    assert ga.get_recent_runs("owner/repo", 1).startswith("ERROR")


@respx.mock
def test_get_recent_runs_formats_output(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    respx.get("https://api.github.com/repos/owner/repo/actions/runs").mock(
        return_value=httpx.Response(
            200,
            json={
                "workflow_runs": [
                    {
                        "id": 1,
                        "name": "CI",
                        "status": "completed",
                        "conclusion": "failure",
                        "head_branch": "main",
                        "head_sha": "abcdef1234",
                        "created_at": "2026-07-01T00:00:00Z",
                    }
                ]
            },
        )
    )
    result = ga.get_recent_runs("owner/repo", 1)
    assert "run 1" in result
    assert "failure" in result
    assert "abcdef1" in result


@respx.mock
def test_get_recent_runs_empty(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    respx.get("https://api.github.com/repos/owner/repo/actions/runs").mock(
        return_value=httpx.Response(200, json={"workflow_runs": []})
    )
    assert ga.get_recent_runs("owner/repo", 1) == "No recent workflow runs found."


@respx.mock
def test_get_run_logs_only_failed_jobs(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    respx.get("https://api.github.com/repos/owner/repo/actions/runs/5/jobs").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobs": [
                    {"id": 10, "name": "build", "conclusion": "success"},
                    {"id": 11, "name": "test", "conclusion": "failure"},
                ]
            },
        )
    )
    respx.get("https://api.github.com/repos/owner/repo/actions/jobs/11/logs").mock(
        return_value=httpx.Response(200, text="AssertionError: boom")
    )
    result = ga.get_run_logs("owner/repo", 5, 1)
    assert "test" in result
    assert "AssertionError" in result
    assert "build" not in result


@respx.mock
def test_get_run_logs_no_failures(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    respx.get("https://api.github.com/repos/owner/repo/actions/runs/5/jobs").mock(
        return_value=httpx.Response(200, json={"jobs": [{"id": 10, "name": "build", "conclusion": "success"}]})
    )
    assert ga.get_run_logs("owner/repo", 5, 1) == "No failed jobs found for run 5."


@respx.mock
def test_get_deploy_diff_formats_files(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    respx.get("https://api.github.com/repos/owner/repo/compare/main...feature").mock(
        return_value=httpx.Response(
            200,
            json={
                "commits": [{}],
                "files": [
                    {
                        "filename": "db.py",
                        "additions": 1,
                        "deletions": 1,
                        "patch": "-POOL_SIZE = 20\n+POOL_SIZE = 2",
                    }
                ],
            },
        )
    )
    result = ga.get_deploy_diff("owner/repo", "main", "feature", 1)
    assert "db.py" in result
    assert "POOL_SIZE" in result


@respx.mock
def test_get_deploy_diff_http_error(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    monkeypatch.setattr("tools._http.time.sleep", lambda s: None)
    respx.get("https://api.github.com/repos/owner/repo/compare/main...feature").mock(return_value=httpx.Response(404))
    assert ga.get_deploy_diff("owner/repo", "main", "feature", 1).startswith("ERROR")


def _fake_config_capturing(captured):
    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["deployment_id"] = deployment_id
        return {"token": ""}
    return fake_config


def test_get_recent_runs_passes_deployment_id_to_config(monkeypatch):
    captured = {}
    monkeypatch.setattr(ga, "_config", _fake_config_capturing(captured))
    ga.get_recent_runs("owner/repo", 1, deployment_id=42)
    assert captured["deployment_id"] == 42


def test_get_run_logs_passes_deployment_id_to_config(monkeypatch):
    captured = {}
    monkeypatch.setattr(ga, "_config", _fake_config_capturing(captured))
    ga.get_run_logs("owner/repo", 5, 1, deployment_id=42)
    assert captured["deployment_id"] == 42


def test_get_deploy_diff_passes_deployment_id_to_config(monkeypatch):
    captured = {}
    monkeypatch.setattr(ga, "_config", _fake_config_capturing(captured))
    ga.get_deploy_diff("owner/repo", "main", "feature", 1, deployment_id=42)
    assert captured["deployment_id"] == 42


def test_get_file_contents_requires_token(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "")
    assert ga.get_file_contents("owner/repo", "x.py", "main", 1).startswith("ERROR")


@respx.mock
def test_get_file_contents_returns_decoded_text(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    content = "line one\nline two\n"
    respx.get("https://api.github.com/repos/owner/repo/contents/tests/x.py").mock(
        return_value=httpx.Response(
            200,
            json={"size": len(content), "encoding": "base64", "content": base64.b64encode(content.encode()).decode()},
        )
    )
    assert ga.get_file_contents("owner/repo", "tests/x.py", "main", 1) == content


@respx.mock
def test_get_file_contents_too_large(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    respx.get("https://api.github.com/repos/owner/repo/contents/big.py").mock(
        return_value=httpx.Response(
            200, json={"size": ga.FILE_CONTENTS_MAX_BYTES + 1, "encoding": "base64", "content": ""}
        )
    )
    result = ga.get_file_contents("owner/repo", "big.py", "main", 1)
    assert result.startswith("ERROR")
    assert "too large" in result


@respx.mock
def test_get_file_contents_directory_errors(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    respx.get("https://api.github.com/repos/owner/repo/contents/some_dir").mock(
        return_value=httpx.Response(200, json=[{"name": "a.py"}, {"name": "b.py"}])
    )
    result = ga.get_file_contents("owner/repo", "some_dir", "main", 1)
    assert result.startswith("ERROR")
    assert "directory" in result


@respx.mock
def test_get_file_contents_http_error(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    monkeypatch.setattr("tools._http.time.sleep", lambda s: None)
    respx.get("https://api.github.com/repos/owner/repo/contents/missing.py").mock(return_value=httpx.Response(404))
    assert ga.get_file_contents("owner/repo", "missing.py", "main", 1).startswith("ERROR")


def test_open_fix_pull_request_requires_token(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "")
    result = ga.open_fix_pull_request("owner/repo", "main", [], "t", "b", 7, 1)
    assert result == {"ok": False, "error": "GITHUB_TOKEN not configured"}


@respx.mock
def test_open_fix_pull_request_happy_path(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    respx.get("https://api.github.com/repos/owner/repo/git/ref/heads/main").mock(
        return_value=httpx.Response(200, json={"object": {"sha": "basesha123"}})
    )
    respx.post("https://api.github.com/repos/owner/repo/git/refs").mock(
        return_value=httpx.Response(201, json={"ref": "refs/heads/phantom-fix/7"})
    )
    respx.get("https://api.github.com/repos/owner/repo/contents/tests/x.py").mock(
        return_value=httpx.Response(200, json={"sha": "filesha456"})
    )
    respx.put("https://api.github.com/repos/owner/repo/contents/tests/x.py").mock(
        return_value=httpx.Response(200, json={"commit": {"sha": "newcommitsha"}})
    )
    respx.post("https://api.github.com/repos/owner/repo/pulls").mock(
        return_value=httpx.Response(201, json={"html_url": "https://github.com/owner/repo/pull/9"})
    )
    result = ga.open_fix_pull_request(
        "owner/repo", "main", [{"path": "tests/x.py", "content": "new content"}], "Fix flaky test", "body", 7, 1,
    )
    assert result == {"ok": True, "pr_url": "https://github.com/owner/repo/pull/9", "branch": "phantom-fix/7"}


@respx.mock
def test_open_fix_pull_request_branch_already_exists(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    monkeypatch.setattr("tools._http.time.sleep", lambda s: None)
    respx.get("https://api.github.com/repos/owner/repo/git/ref/heads/main").mock(
        return_value=httpx.Response(200, json={"object": {"sha": "basesha123"}})
    )
    respx.post("https://api.github.com/repos/owner/repo/git/refs").mock(return_value=httpx.Response(422))
    result = ga.open_fix_pull_request(
        "owner/repo", "main", [{"path": "tests/x.py", "content": "new content"}], "Fix flaky test", "body", 7, 1,
    )
    assert result["ok"] is False
    assert "already exists" in result["error"]


@respx.mock
def test_open_fix_pull_request_file_missing_on_branch(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    monkeypatch.setattr("tools._http.time.sleep", lambda s: None)
    respx.get("https://api.github.com/repos/owner/repo/git/ref/heads/main").mock(
        return_value=httpx.Response(200, json={"object": {"sha": "basesha123"}})
    )
    respx.post("https://api.github.com/repos/owner/repo/git/refs").mock(return_value=httpx.Response(201, json={}))
    respx.get("https://api.github.com/repos/owner/repo/contents/tests/x.py").mock(return_value=httpx.Response(404))
    result = ga.open_fix_pull_request(
        "owner/repo", "main", [{"path": "tests/x.py", "content": "new content"}], "Fix flaky test", "body", 7, 1,
    )
    assert result["ok"] is False
    assert "does not exist" in result["error"]
