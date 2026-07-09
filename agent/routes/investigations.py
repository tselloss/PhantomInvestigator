"""Investigation history/detail/stats API for the operator UI. Mounted under
/api by main.py -- literal-path routes (stats) are declared before the
{investigation_id} routes so they aren't shadowed by the int path param."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

import investigations as store
from routes.auth import get_current_user
from tools import jira

router = APIRouter(prefix="/investigations")


@router.get("")
def list_investigations(
    limit: int = 20,
    offset: int = 0,
    source: str | None = None,
    status: str | None = None,
    deployment_id: int | None = None,
    user: dict = Depends(get_current_user),
):
    return store.list_recent(
        user["user_id"], limit=limit, offset=offset, source=source, status=status, deployment_id=deployment_id
    )


@router.get("/stats")
def investigation_stats(days: int = 7, deployment_id: int | None = None, user: dict = Depends(get_current_user)):
    return store.stats(user["user_id"], days=days, deployment_id=deployment_id)


@router.get("/{investigation_id}")
def get_investigation(investigation_id: int, user: dict = Depends(get_current_user)):
    item = store.get_by_id(investigation_id, user["user_id"])
    if not item:
        raise HTTPException(404, "investigation not found")
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
    """Executes a pending high-stakes write (currently only a Jira comment
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
