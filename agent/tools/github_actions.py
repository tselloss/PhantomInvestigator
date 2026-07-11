"""Query GitHub Actions runs/logs and real deploy diffs via the GitHub REST API.
Replaces the demo's fake diff in deploys.py with the real compare API.
Truncated so a noisy log/diff can't blow the context window."""
import os

import httpx

import demo_data
import integration_credentials
import users
from ._http import request_with_retry

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"


def _config(user_id: int, deployment_id: int | None = None, client_id: int | None = None) -> dict:
    override = integration_credentials.resolve_credentials(
        "github", user_id, deployment_id=deployment_id, client_id=client_id
    ) or {}
    return {"token": override.get("token") or GITHUB_TOKEN}


def _headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_recent_runs(repo: str, user_id: int, deployment_id: int | None = None) -> str:
    """repo: 'owner/name'. Returns the most recent workflow runs with status/conclusion."""
    cfg = _config(user_id, deployment_id=deployment_id)
    if not cfg["token"]:
        if users.get_demo_mode(user_id):
            return demo_data.github_recent_runs(repo)
        return "ERROR: GITHUB_TOKEN not configured"
    try:
        resp = request_with_retry(
            "GET",
            f"{GITHUB_API}/repos/{repo}/actions/runs",
            headers=_headers(cfg["token"]),
            params={"per_page": 10},
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        return f"ERROR fetching workflow runs for {repo}: {e}"

    runs = resp.json().get("workflow_runs", [])
    lines = [
        f"- run {r['id']} | {r['name']} | {r['status']}/{r['conclusion']} | "
        f"branch={r['head_branch']} | sha={r['head_sha'][:7]} | {r['created_at']}"
        for r in runs
    ]
    return "\n".join(lines)[:3000] if lines else "No recent workflow runs found."


def get_run_logs(repo: str, run_id: int, user_id: int, deployment_id: int | None = None) -> str:
    """Fetch logs for the failed jobs in a workflow run."""
    cfg = _config(user_id, deployment_id=deployment_id)
    if not cfg["token"]:
        if users.get_demo_mode(user_id):
            return demo_data.github_run_logs(repo, run_id)
        return "ERROR: GITHUB_TOKEN not configured"
    try:
        jobs_resp = request_with_retry(
            "GET",
            f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}/jobs",
            headers=_headers(cfg["token"]),
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        return f"ERROR fetching jobs for run {run_id}: {e}"

    failed_jobs = [j for j in jobs_resp.json().get("jobs", []) if j.get("conclusion") == "failure"]
    if not failed_jobs:
        return f"No failed jobs found for run {run_id}."

    chunks = []
    for job in failed_jobs[:3]:
        try:
            log_resp = request_with_retry(
                "GET",
                f"{GITHUB_API}/repos/{repo}/actions/jobs/{job['id']}/logs",
                headers=_headers(cfg["token"]),
                timeout=10.0,
                follow_redirects=True,
            )
            chunks.append(f"--- job: {job['name']} ---\n{log_resp.text[-1500:]}")
        except httpx.HTTPError as e:
            chunks.append(f"--- job: {job['name']} ---\nERROR fetching logs: {e}")
    return "\n\n".join(chunks)[:4000]


def get_deploy_diff(repo: str, base: str, head: str, user_id: int, deployment_id: int | None = None) -> str:
    """Real GitHub compare API: GET /repos/{repo}/compare/{base}...{head}."""
    cfg = _config(user_id, deployment_id=deployment_id)
    if not cfg["token"]:
        if users.get_demo_mode(user_id):
            return demo_data.github_deploy_diff(repo, base, head)
        return "ERROR: GITHUB_TOKEN not configured"
    try:
        resp = request_with_retry(
            "GET",
            f"{GITHUB_API}/repos/{repo}/compare/{base}...{head}",
            headers=_headers(cfg["token"]),
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        return f"ERROR comparing {base}...{head} on {repo}: {e}"

    data = resp.json()
    lines = [f"{len(data.get('commits', []))} commits, {len(data.get('files', []))} files changed"]
    for f in data.get("files", [])[:20]:
        lines.append(f"- {f['filename']} (+{f.get('additions', 0)}/-{f.get('deletions', 0)})")
        if f.get("patch"):
            lines.append(f["patch"][:500])
    return "\n".join(lines)[:4000]
