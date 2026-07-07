"""Webhook entry points for real-source triggers: Jira ticket events and
GitHub Actions failures. Both hand off to the agent loop as a background
task -- webhook callers expect a fast response, not a 20-40s wait for the
investigation to finish."""
import hashlib
import hmac
import os

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

import investigations
from loop import run_agent
from tools import jira

router = APIRouter(prefix="/webhooks")

JIRA_WEBHOOK_SECRET = os.environ.get("JIRA_WEBHOOK_SECRET", "")
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")


def _investigate_and_report(source: str, source_ref: str | None, alert_text: str, jira_key: str | None = None):
    """Runs inside a BackgroundTasks worker (not the request thread) -- fine
    to block here. Records the run for the UI's activity feed, and posts the
    postmortem back to Jira if triggered by a ticket."""
    investigation_id = investigations.start(source, source_ref, alert_text)
    result = run_agent(alert_text)
    pm = result.get("postmortem") if result else None
    investigations.finish(investigation_id, "done" if pm else "partial", result or {})
    if jira_key and pm:
        body = (
            f"[Phantom Investigator] {pm['title']}\n\n"
            f"Root cause ({pm['confidence']:.0%} confidence): {pm['root_cause']}\n\n"
            f"Suggested fix: {pm['suggested_fix']}"
        )
        jira.post_comment(jira_key, body)


@router.post("/jira")
async def jira_webhook(request: Request, background_tasks: BackgroundTasks, secret: str = ""):
    if not JIRA_WEBHOOK_SECRET or not hmac.compare_digest(secret, JIRA_WEBHOOK_SECRET):
        raise HTTPException(401, "invalid webhook secret")

    payload = await request.json()
    issue = payload.get("issue", {})
    key = issue.get("key")
    if not key:
        raise HTTPException(400, "no issue key in payload")

    summary = issue.get("fields", {}).get("summary", "")
    alert_text = f"Jira ticket {key}: {summary}. Investigate."

    background_tasks.add_task(_investigate_and_report, "jira", key, alert_text, key)
    return {"accepted": True, "key": key}


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(default=""),
):
    body = await request.body()
    if not GITHUB_WEBHOOK_SECRET:
        raise HTTPException(401, "webhook secret not configured")
    expected = "sha256=" + hmac.new(GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_hub_signature_256):
        raise HTTPException(401, "invalid signature")

    payload = await request.json()
    run = payload.get("workflow_run", {})
    if run.get("conclusion") != "failure":
        return {"accepted": False, "reason": "not a failed run"}

    repo = payload.get("repository", {}).get("full_name", GITHUB_REPO)
    alert_text = (
        f"GitHub Actions run {run.get('id')} ('{run.get('name')}') failed on "
        f"{repo} branch {run.get('head_branch')} (sha {run.get('head_sha', '')[:7]}). Investigate."
    )
    background_tasks.add_task(_investigate_and_report, "github", str(run.get("id")), alert_text)
    return {"accepted": True, "run_id": run.get("id")}
