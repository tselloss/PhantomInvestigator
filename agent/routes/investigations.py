"""Investigation history/detail/stats API for the operator UI. Mounted under
/api by main.py -- literal-path routes (stats) are declared before the
{investigation_id} routes so they aren't shadowed by the int path param."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import investigations as store
from routes.auth import get_current_user

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


class ReviewedUpdate(BaseModel):
    reviewed: bool


@router.patch("/{investigation_id}")
def update_investigation(investigation_id: int, update: ReviewedUpdate, user: dict = Depends(get_current_user)):
    item = store.set_reviewed(investigation_id, user["user_id"], update.reviewed)
    if not item:
        raise HTTPException(404, "investigation not found")
    return item
