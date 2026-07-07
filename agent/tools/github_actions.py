"""Query GitHub Actions runs/logs and real deploy diffs via the GitHub REST API.
Replaces the demo's fake diff in deploys.py with the real compare API.
Truncated so a noisy log/diff can't blow the context window."""
import os

import httpx

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_recent_runs(repo: str) -> str:
    """repo: 'owner/name'. Returns the most recent workflow runs with status/conclusion."""
    if not GITHUB_TOKEN:
        return "ERROR: GITHUB_TOKEN not configured"
    try:
        resp = httpx.get(
            f"{GITHUB_API}/repos/{repo}/actions/runs",
            headers=_headers(),
            params={"per_page": 10},
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"ERROR fetching workflow runs for {repo}: {e}"

    runs = resp.json().get("workflow_runs", [])
    lines = [
        f"- run {r['id']} | {r['name']} | {r['status']}/{r['conclusion']} | "
        f"branch={r['head_branch']} | sha={r['head_sha'][:7]} | {r['created_at']}"
        for r in runs
    ]
    return "\n".join(lines)[:3000] if lines else "No recent workflow runs found."


def get_run_logs(repo: str, run_id: int) -> str:
    """Fetch logs for the failed jobs in a workflow run."""
    if not GITHUB_TOKEN:
        return "ERROR: GITHUB_TOKEN not configured"
    try:
        jobs_resp = httpx.get(
            f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}/jobs",
            headers=_headers(),
            timeout=10.0,
        )
        jobs_resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"ERROR fetching jobs for run {run_id}: {e}"

    failed_jobs = [j for j in jobs_resp.json().get("jobs", []) if j.get("conclusion") == "failure"]
    if not failed_jobs:
        return f"No failed jobs found for run {run_id}."

    chunks = []
    for job in failed_jobs[:3]:
        try:
            log_resp = httpx.get(
                f"{GITHUB_API}/repos/{repo}/actions/jobs/{job['id']}/logs",
                headers=_headers(),
                timeout=10.0,
                follow_redirects=True,
            )
            log_resp.raise_for_status()
            chunks.append(f"--- job: {job['name']} ---\n{log_resp.text[-1500:]}")
        except httpx.HTTPError as e:
            chunks.append(f"--- job: {job['name']} ---\nERROR fetching logs: {e}")
    return "\n\n".join(chunks)[:4000]


def get_deploy_diff(repo: str, base: str, head: str) -> str:
    """Real GitHub compare API: GET /repos/{repo}/compare/{base}...{head}."""
    if not GITHUB_TOKEN:
        return "ERROR: GITHUB_TOKEN not configured"
    try:
        resp = httpx.get(
            f"{GITHUB_API}/repos/{repo}/compare/{base}...{head}",
            headers=_headers(),
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"ERROR comparing {base}...{head} on {repo}: {e}"

    data = resp.json()
    lines = [f"{len(data.get('commits', []))} commits, {len(data.get('files', []))} files changed"]
    for f in data.get("files", [])[:20]:
        lines.append(f"- {f['filename']} (+{f.get('additions', 0)}/-{f.get('deletions', 0)})")
        if f.get("patch"):
            lines.append(f["patch"][:500])
    return "\n".join(lines)[:4000]
