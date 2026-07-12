"""Webhook entry points for real-source triggers: Jira ticket events,
GitHub Actions failures, and Azure DevOps work item events. All hand off to
the agent loop as a background task -- webhook callers expect a fast
response, not a 20-40s wait for the investigation to finish."""
import hashlib
import hmac
import os
import re

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

import billing
import clients
import fix_proposals
import investigations
from loop import run_agent

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks")

JIRA_WEBHOOK_SECRET = os.environ.get("JIRA_WEBHOOK_SECRET", "")
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
AZURE_DEVOPS_WEBHOOK_SECRET = os.environ.get("AZURE_DEVOPS_WEBHOOK_SECRET", "")

# Azure DevOps Service Hooks fire on every field edit, not just meaningful
# ones -- restrict to work item types that actually mean "something's
# broken" so routine backlog grooming doesn't trigger an investigation.
# "Issue" covers the Basic process template, which has no "Bug" type at all.
AZURE_DEVOPS_BUG_TYPES = {"bug", "issue"}


def _resolve_deployment(finder, key: str | None) -> tuple[int | None, int | None, str]:
    """Looks up a deployment by Jira project key or GitHub repo and, if
    found, returns its id, its owner_user_id, and a short note to prepend to
    alert_text -- tools are stateless w.r.t. the investigation, so this is
    how the model learns which deployment it's looking at (same as a Jira
    key today). finder() is one of the unscoped find_deployment_by_* lookups
    (webhooks authenticate via a shared secret, not a logged-in user, so
    there's no owner to filter by here) -- the deployment's own owner_user_id
    is what everything downstream (the investigation, credential
    resolution, the AI key used) gets attributed to."""
    if not key:
        return None, None, ""
    deployment = finder(key)
    if not deployment:
        return None, None, ""
    owner_user_id = deployment["owner_user_id"]
    client = clients.get_client(deployment["client_id"], owner_user_id)
    client_name = client["name"] if client else f"client {deployment['client_id']}"
    note = f"Deployment: {client_name} / {deployment['label']} (id {deployment['id']}). "
    return deployment["id"], owner_user_id, note


def _investigate_and_report(
    source: str,
    source_ref: str | None,
    alert_text: str,
    jira_key: str | None = None,
    deployment_id: int | None = None,
    owner_user_id: int | None = None,
    azure_devops_work_item_id: int | None = None,
):
    """Runs inside a BackgroundTasks worker (not the request thread) -- fine
    to block here. Records the run for the UI's activity feed, and posts the
    postmortem back to Jira if triggered by a ticket.

    Skips entirely when owner_user_id is None -- an unresolved deployment
    (the alert's project/repo doesn't match any registered deployment) has
    no owner to attribute the investigation to and no way to pick whose AI
    key/credentials should fund it, so there's nothing safe to run.

    Checks for a recent duplicate first (e.g. a retried webhook delivery for
    the same ticket/run) and skips straight out if found -- retries are
    common with webhooks, and re-running the full agent loop for one would
    spend the operator's AI credits on nothing new."""
    if owner_user_id is None:
        log.info("webhook.no_owner_resolved", source=source, source_ref=source_ref)
        return

    duplicate = investigations.find_recent_duplicate(source, source_ref, deployment_id, alert_text, owner_user_id)
    if duplicate is not None:
        log.info(
            "webhook.deduped", source=source, source_ref=source_ref,
            existing_investigation_id=duplicate["id"],
        )
        return

    budget = billing.check_budget(owner_user_id)
    if not budget["allowed"]:
        log.info(
            "webhook.budget_exceeded", source=source, source_ref=source_ref, owner_user_id=owner_user_id,
            spent_usd=budget["spent_usd"], limit_usd=budget["limit_usd"],
        )
        return

    investigation_id = investigations.start(source, source_ref, alert_text, owner_user_id, deployment_id=deployment_id)
    loop_alert_text = clients.build_loop_alert_text(alert_text, investigation_id, deployment_id, owner_user_id)
    result = run_agent(loop_alert_text, owner_user_id, deployment_id=deployment_id)
    pm = result.get("postmortem") if result else None

    # Posting back to the ticket is a high-stakes, externally-visible write --
    # instead of firing it unattended the moment the loop finishes, queue it
    # as a pending_action for an operator to approve or dismiss from the UI
    # (see routes/investigations.py's approve-post/dismiss-post).
    pending_action = None
    if pm:
        body = (
            f"[Phantom Investigator] {pm['title']}\n\n"
            f"Root cause ({pm['confidence']:.0%} confidence): {pm['root_cause']}\n\n"
            f"Suggested fix: {pm['suggested_fix']}"
        )
        if jira_key:
            pending_action = {"type": "jira_comment", "key": jira_key, "body": body}
        elif azure_devops_work_item_id:
            pending_action = {"type": "azure_devops_comment", "work_item_id": azure_devops_work_item_id, "body": body}

    # Same idea as pending_action above, for a proposed code fix instead of
    # a ticket comment -- see fix_proposals.build_pending_fix_action for the
    # gates (deployment must opt in via allowed_base_branches, every
    # proposed file must have actually been read this run). Only looks up
    # the deployment at all when there's a postmortem to fold it into --
    # same "nothing to do" short-circuit pending_action already has above.
    pending_fix_action = None
    if pm:
        deployment = clients.get_deployment(deployment_id, owner_user_id) if deployment_id else None
        pending_fix_action = fix_proposals.build_pending_fix_action(
            pm, deployment, result.get("files_read", []), owner_user_id
        )

    investigations.finish(
        investigation_id, "done" if pm else "partial", result or {},
        pending_action=pending_action, pending_fix_action=pending_fix_action,
    )


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
    project_key = issue.get("fields", {}).get("project", {}).get("key")
    deployment_id, owner_user_id, deployment_note = _resolve_deployment(clients.find_deployment_by_jira_project, project_key)
    alert_text = f"{deployment_note}Jira ticket {key}: {summary}. Investigate."

    background_tasks.add_task(_investigate_and_report, "jira", key, alert_text, key, deployment_id, owner_user_id)
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
    deployment_id, owner_user_id, deployment_note = _resolve_deployment(clients.find_deployment_by_github_repo, repo)
    alert_text = (
        f"{deployment_note}GitHub Actions run {run.get('id')} ('{run.get('name')}') failed on "
        f"{repo} branch {run.get('head_branch')} (sha {run.get('head_sha', '')[:7]}). Investigate."
    )
    background_tasks.add_task(
        _investigate_and_report, "github", str(run.get("id")), alert_text, None, deployment_id, owner_user_id
    )
    return {"accepted": True, "run_id": run.get("id")}


def _parse_azure_devops_org(url: str) -> str | None:
    """Work item URLs come in either the current dev.azure.com/{org}/...
    shape or the legacy {org}.visualstudio.com/... shape, tenant-dependent
    -- try both rather than assuming one."""
    match = re.match(r"https://dev\.azure\.com/([^/]+)/", url) or re.match(r"https://([^.]+)\.visualstudio\.com/", url)
    return match.group(1) if match else None


@router.post("/azure_devops")
async def azure_devops_webhook(request: Request, background_tasks: BackgroundTasks, secret: str = ""):
    if not AZURE_DEVOPS_WEBHOOK_SECRET or not hmac.compare_digest(secret, AZURE_DEVOPS_WEBHOOK_SECRET):
        raise HTTPException(401, "invalid webhook secret")

    payload = await request.json()
    event_type = payload.get("eventType", "")
    if event_type not in ("workitem.created", "workitem.updated"):
        return {"accepted": False, "reason": f"ignoring event type {event_type!r}"}

    resource = payload.get("resource", {})
    work_item_id = resource.get("workItemId") or resource.get("id")
    if not work_item_id:
        raise HTTPException(400, "no work item id in payload")

    # workitem.updated's top-level resource.fields is a {oldValue, newValue}
    # diff of only the fields that changed -- e.g. a State-only change has no
    # System.Title/WorkItemType/TeamProject in it at all. The full current
    # snapshot (plain values) is under resource.revision.fields instead.
    # workitem.created has no "revision" key and resource.fields IS already
    # the full snapshot, so falling back to it there is correct too.
    fields = resource.get("revision", {}).get("fields") or resource.get("fields", {})
    work_item_type = fields.get("System.WorkItemType", "")
    if work_item_type.lower() not in AZURE_DEVOPS_BUG_TYPES:
        return {"accepted": False, "reason": f"ignoring work item type {work_item_type!r}"}

    title = fields.get("System.Title", "")
    team_project = fields.get("System.TeamProject", "")
    organization = _parse_azure_devops_org(resource.get("url", ""))
    project_key = f"{organization}/{team_project}" if organization and team_project else None

    deployment_id, owner_user_id, deployment_note = _resolve_deployment(
        clients.find_deployment_by_azure_devops_project, project_key
    )
    alert_text = f"{deployment_note}Azure DevOps work item {work_item_id} ({work_item_type}): {title}. Investigate."

    background_tasks.add_task(
        _investigate_and_report, "azure_devops", str(work_item_id), alert_text, None,
        deployment_id, owner_user_id, azure_devops_work_item_id=work_item_id,
    )
    return {"accepted": True, "work_item_id": work_item_id}
