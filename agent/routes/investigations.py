"""Investigation history/detail/stats API for the operator UI. Mounted under
/api by main.py -- literal-path routes (stats) are declared before the
{investigation_id} routes so they aren't shadowed by the int path param."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import investigations as store

router = APIRouter(prefix="/investigations")


@router.get("")
def list_investigations(limit: int = 20, offset: int = 0, source: str | None = None, status: str | None = None):
    return store.list_recent(limit=limit, offset=offset, source=source, status=status)


@router.get("/stats")
def investigation_stats(days: int = 7):
    return store.stats(days=days)


@router.get("/{investigation_id}")
def get_investigation(investigation_id: int):
    item = store.get_by_id(investigation_id)
    if not item:
        raise HTTPException(404, "investigation not found")
    return item


class ReviewedUpdate(BaseModel):
    reviewed: bool


@router.patch("/{investigation_id}")
def update_investigation(investigation_id: int, update: ReviewedUpdate):
    item = store.set_reviewed(investigation_id, update.reviewed)
    if not item:
        raise HTTPException(404, "investigation not found")
    return item
