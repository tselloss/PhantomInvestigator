import httpx
import respx

from tools import github_actions as ga


def test_get_recent_runs_requires_token(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "")
    assert ga.get_recent_runs("owner/repo").startswith("ERROR")


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
    result = ga.get_recent_runs("owner/repo")
    assert "run 1" in result
    assert "failure" in result
    assert "abcdef1" in result


@respx.mock
def test_get_recent_runs_empty(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    respx.get("https://api.github.com/repos/owner/repo/actions/runs").mock(
        return_value=httpx.Response(200, json={"workflow_runs": []})
    )
    assert ga.get_recent_runs("owner/repo") == "No recent workflow runs found."


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
    result = ga.get_run_logs("owner/repo", 5)
    assert "test" in result
    assert "AssertionError" in result
    assert "build" not in result


@respx.mock
def test_get_run_logs_no_failures(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    respx.get("https://api.github.com/repos/owner/repo/actions/runs/5/jobs").mock(
        return_value=httpx.Response(200, json={"jobs": [{"id": 10, "name": "build", "conclusion": "success"}]})
    )
    assert ga.get_run_logs("owner/repo", 5) == "No failed jobs found for run 5."


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
    result = ga.get_deploy_diff("owner/repo", "main", "feature")
    assert "db.py" in result
    assert "POOL_SIZE" in result


@respx.mock
def test_get_deploy_diff_http_error(monkeypatch):
    monkeypatch.setattr(ga, "GITHUB_TOKEN", "tok")
    monkeypatch.setattr("tools._http.time.sleep", lambda s: None)
    respx.get("https://api.github.com/repos/owner/repo/compare/main...feature").mock(return_value=httpx.Response(404))
    assert ga.get_deploy_diff("owner/repo", "main", "feature").startswith("ERROR")
