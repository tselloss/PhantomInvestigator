"""Runbook listing + re-ingest trigger for the operator UI."""
from fastapi import APIRouter, Depends

from rag.ingest import list_runbooks
from rag.ingest import main as ingest_main
from routes.auth import get_current_user

router = APIRouter(prefix="/runbooks")


@router.get("")
def get_runbooks(user: dict = Depends(get_current_user)):
    return list_runbooks(user["user_id"])


@router.post("/ingest")
def trigger_ingest(user: dict = Depends(get_current_user)):
    embedded = ingest_main(user["user_id"])
    return {"embedded_chunks": embedded}
