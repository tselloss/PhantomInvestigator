"""Query GitHub Actions runs/logs/deploy diffs, read a file's current content,
and (approve-fix route only, never model-callable) open a fix pull request,
via the GitHub REST API. The read-side functions truncate a noisy log/diff so
it can't blow the context window; get_file_contents deliberately does NOT --
see its docstring."""
import base64
import os

import httpx

import integration_credentials
from ._http import request_with_retry

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"
# get_file_contents never returns a partial file -- past this size it errors
# out instead, since a silently truncated "complete file" is exactly what
# makes an LLM-authored proposed_fix_files entry dangerous (the model would
# confidently "complete" content it never actually saw).
FILE_CONTENTS_MAX_BYTES = 80_000


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


def get_file_contents(repo: str, path: str, ref: str, user_id: int, deployment_id: int | None = None) -> str:
    """Full current content of one file at a ref. Model-callable: this is how
    the model grounds a proposed_fix_files edit in the file's real content
    instead of guessing. Unlike every other read tool here, this never
    silently truncates -- past FILE_CONTENTS_MAX_BYTES it returns a clear
    error instead of a partial body, because a truncated "full" file is
    unsafe input to a fix that gets committed verbatim."""
    cfg = _config(user_id, deployment_id=deployment_id)
    if not cfg["token"]:
        return "ERROR: GITHUB_TOKEN not configured"
    try:
        resp = request_with_retry(
            "GET",
            f"{GITHUB_API}/repos/{repo}/contents/{path}",
            headers=_headers(cfg["token"]),
            params={"ref": ref},
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        return f"ERROR fetching {path}@{ref} from {repo}: {e}"

    data = resp.json()
    if isinstance(data, list):
        return f"ERROR: {path} is a directory, not a file"
    size = data.get("size", 0)
    if size > FILE_CONTENTS_MAX_BYTES:
        return (
            f"ERROR: file too large for full-content read ({size} bytes > "
            f"{FILE_CONTENTS_MAX_BYTES}) -- do not propose a fix for this file"
        )
    if data.get("encoding") != "base64" or "content" not in data:
        return f"ERROR: unexpected response reading {path}@{ref} (not a base64-encoded file)"
    try:
        return base64.b64decode(data["content"]).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as e:
        return f"ERROR: could not decode {path}@{ref} as UTF-8 text: {e}"


def _ref_sha(repo: str, branch: str, token: str) -> str:
    resp = request_with_retry(
        "GET", f"{GITHUB_API}/repos/{repo}/git/ref/heads/{branch}", headers=_headers(token), timeout=10.0,
    )
    return resp.json()["object"]["sha"]


def _file_sha(repo: str, path: str, branch: str, token: str) -> str | None:
    """Current sha of path on branch, needed for the Contents API PUT's
    optimistic-concurrency check on an update. None if the file doesn't
    exist on that branch -- Phase 1 only supports editing files the model
    already read via get_file_contents, so that's always caller error, never
    "create this new file"."""
    try:
        resp = request_with_retry(
            "GET", f"{GITHUB_API}/repos/{repo}/contents/{path}",
            headers=_headers(token), params={"ref": branch}, timeout=10.0,
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise
    return resp.json()["sha"]


def open_fix_pull_request(
    repo: str, target_branch: str, files: list[dict], title: str, body: str, investigation_id: int,
    user_id: int, deployment_id: int | None = None,
) -> dict:
    """Never registered as a model tool (see tools/__init__.py) -- only ever
    called from the approve-fix route after an operator has reviewed the
    diff. Unlike every model-facing function in this module, this raises on
    unexpected API failures rather than returning an ERROR string; the route
    is responsible for translating a raise or an {"ok": False, ...} result
    into an HTTP error. Sequence: branch off target_branch's current tip ->
    one commit per file (the Contents API has no atomic multi-file commit
    without the lower-level Git Data tree/commit API, not worth it for
    Phase 1) -> open the PR. Never force-pushes: if the branch already
    exists, this fails rather than overwriting a ref it may not have
    created."""
    cfg = _config(user_id, deployment_id=deployment_id)
    if not cfg["token"]:
        return {"ok": False, "error": "GITHUB_TOKEN not configured"}
    token = cfg["token"]
    branch = f"phantom-fix/{investigation_id}"
    try:
        base_sha = _ref_sha(repo, target_branch, token)
        try:
            request_with_retry(
                "POST", f"{GITHUB_API}/repos/{repo}/git/refs",
                headers=_headers(token),
                json={"ref": f"refs/heads/{branch}", "sha": base_sha},
                timeout=10.0,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                return {"ok": False, "error": f"branch {branch!r} already exists on {repo} -- not overwriting it"}
            raise

        for f in files:
            file_sha = _file_sha(repo, f["path"], branch, token)
            if file_sha is None:
                return {
                    "ok": False,
                    "error": f"{f['path']} does not exist on {target_branch} -- cannot edit a file that isn't there",
                }
            request_with_retry(
                "PUT", f"{GITHUB_API}/repos/{repo}/contents/{f['path']}",
                headers=_headers(token),
                json={
                    "message": f"Phantom Investigator: {title}",
                    "content": base64.b64encode(f["content"].encode("utf-8")).decode("ascii"),
                    "sha": file_sha,
                    "branch": branch,
                },
                timeout=10.0,
            )

        pr_resp = request_with_retry(
            "POST", f"{GITHUB_API}/repos/{repo}/pulls",
            headers=_headers(token),
            json={"title": title, "body": body, "head": branch, "base": target_branch},
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        return {"ok": False, "error": f"GitHub API error opening fix PR on {repo}: {e}"}

    pr = pr_resp.json()
    return {"ok": True, "pr_url": pr.get("html_url"), "branch": branch}
