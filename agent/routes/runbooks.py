"""Runbook listing + re-ingest trigger for the operator UI."""
from fastapi import APIRouter

from rag.ingest import list_runbooks
from rag.ingest import main as ingest_main

router = APIRouter(prefix="/runbooks")


@router.get("")
def get_runbooks():
    return list_runbooks()


@router.post("/ingest")
def trigger_ingest():
    embedded = ingest_main()
    return {"embedded_chunks": embedded}
