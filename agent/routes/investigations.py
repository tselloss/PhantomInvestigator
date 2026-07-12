"""Investigation history/detail/stats API for the operator UI. Mounted under
/api by main.py -- literal-path routes (stats) are declared before the
{investigation_id} routes so they aren't shadowed by the int path param."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

import clients
import investigations as store
from routes.auth import get_current_user
from tools import azure_devops, github_actions, jira

router = APIRouter(prefix="/investigations")


@router.get("")
def list_investigations(
    limit: int = 20,
    offset: int = 0,
    source: str | None = None,
    status: str | None = None,
    deployment_id: int | None = None,
    reviewed: bool | None = None,
    user: dict = Depends(get_current_user),
):
    return store.list_recent(
        user["user_id"], limit=limit, offset=offset, source=source, status=status,
        deployment_id=deployment_id, reviewed=reviewed,
    )


@router.get("/stats")
def investigation_stats(days: int = 7, deployment_id: int | None = None, user: dict = Depends(get_current_user)):
    return store.stats(user["user_id"], days=days, deployment_id=deployment_id)


@router.get("/{investigation_id}")
def get_investigation(investigation_id: int, user: dict = Depends(get_current_user)):
    item = store.get_by_id(investigation_id, user["user_id"])
    if not item:
        raise HTTPException(404, "investigation not found")
    if item["source"] == "jira" and item["source_ref"]:
        item["jira_url"] = jira.issue_url(item["source_ref"], user["user_id"], deployment_id=item.get("deployment_id"))
    return item


FEEDBACK_RATINGS = {"correct", "partial", "incorrect"}


class FeedbackUpdate(BaseModel):
    reviewed: bool
    feedback_rating: str | None = None
    feedback_notes: str | None = None

    @field_validator("feedback_rating")
    @classmethod
    def _valid_rating(cls, v):
        if v is not None and v not in FEEDBACK_RATINGS:
            raise ValueError(f"feedback_rating must be one of {sorted(FEEDBACK_RATINGS)}")
        return v


@router.patch("/{investigation_id}")
def update_investigation(investigation_id: int, update: FeedbackUpdate, user: dict = Depends(get_current_user)):
    item = store.set_feedback(
        investigation_id, user["user_id"], update.reviewed, update.feedback_rating, update.feedback_notes
    )
    if not item:
        raise HTTPException(404, "investigation not found")
    return item


@router.post("/{investigation_id}/approve-post")
def approve_pending_post(investigation_id: int, user: dict = Depends(get_current_user)):
    """Executes a pending high-stakes write (a Jira or Azure DevOps comment
    queued by the webhook path, see routes/webhooks.py) that was held for
    operator approval instead of firing unattended, then marks it resolved."""
    item = store.get_by_id(investigation_id, user["user_id"])
    if not item:
        raise HTTPException(404, "investigation not found")
    pending = item.get("pending_action")
    if not pending:
        raise HTTPException(400, "no pending action on this investigation")

    if pending["type"] == "jira_comment":
        jira.post_comment(pending["key"], pending["body"], user["user_id"], deployment_id=item.get("deployment_id"))
    elif pending["type"] == "azure_devops_comment":
        azure_devops.post_comment(
            pending["work_item_id"], pending["body"], user["user_id"], deployment_id=item.get("deployment_id")
        )
    else:
        raise HTTPException(500, f"unknown pending_action type: {pending['type']}")

    return store.resolve_pending_action(investigation_id, user["user_id"])


@router.post("/{investigation_id}/dismiss-post")
def dismiss_pending_post(investigation_id: int, user: dict = Depends(get_current_user)):
    """Discards a pending high-stakes write without executing it."""
    item = store.get_by_id(investigation_id, user["user_id"])
    if not item:
        raise HTTPException(404, "investigation not found")
    if not item.get("pending_action"):
        raise HTTPException(400, "no pending action on this investigation")
    return store.resolve_pending_action(investigation_id, user["user_id"])


class ApproveFixRequest(BaseModel):
    target_branch: str | None = None


@router.post("/{investigation_id}/approve-fix")
def approve_pending_fix(investigation_id: int, body: ApproveFixRequest, user: dict = Depends(get_current_user)):
    """Executes a pending code-fix action (push a branch, commit the
    proposed file(s), open a PR -- see fix_proposals.py/github_actions.py)
    that was held for operator approval, then marks it resolved.

    target_branch is re-validated against the deployment's LIVE
    allowed_base_branches, not the snapshot captured in pending_fix_action
    at proposal time -- an operator could have edited the allowlist in the
    time between proposal and approval, and the allowlist is the actual
    authorization boundary, not whatever was true when the proposal was
    built."""
    item = store.get_by_id(investigation_id, user["user_id"])
    if not item:
        raise HTTPException(404, "investigation not found")
    pending = item.get("pending_fix_action")
    if not pending:
        raise HTTPException(400, "no pending fix action on this investigation")

    deployment = clients.get_deployment(item.get("deployment_id"), user["user_id"]) if item.get("deployment_id") else None
    allowed = (deployment or {}).get("allowed_base_branches") or []
    target_branch = body.target_branch or pending.get("default_branch")
    if target_branch not in allowed:
        raise HTTPException(400, f"{target_branch!r} is not in this deployment's allowed base branches")

    result = github_actions.open_fix_pull_request(
        pending["repo"], target_branch, pending["files"], pending["pr_title"], pending["pr_body"],
        investigation_id, user["user_id"], deployment_id=item.get("deployment_id"),
    )
    if not result["ok"]:
        raise HTTPException(502, result["error"])

    resolved = store.resolve_pending_fix_action(investigation_id, user["user_id"])
    return {**resolved, "pr_url": result["pr_url"]}


@router.post("/{investigation_id}/dismiss-fix")
def dismiss_pending_fix(investigation_id: int, user: dict = Depends(get_current_user)):
    """Discards a pending code-fix action without pushing anything."""
    item = store.get_by_id(investigation_id, user["user_id"])
    if not item:
        raise HTTPException(404, "investigation not found")
    if not item.get("pending_fix_action"):
        raise HTTPException(400, "no pending fix action on this investigation")
    return store.resolve_pending_fix_action(investigation_id, user["user_id"])
