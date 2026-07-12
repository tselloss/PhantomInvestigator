"""Aggregated recent bugs/tasks (Jira issues, Azure DevOps work items,
Zendesk tickets) for a client, across whichever of those it has configured
-- powers the Clients page's "Bugs & tasks" section. Split out from
clients.py the same way client_integrations.py/checkin.py/diagnostics.py
are: a distinct sub-domain with its own logic (settings.py), just nested
under /clients/{client_id} instead of top-level."""
from fastapi import APIRouter, Depends, HTTPException

import clients
import settings as integration_settings
from routes.auth import get_current_user

router = APIRouter(prefix="/clients/{client_id}/tickets")


@router.get("")
def list_client_tickets(client_id: int, days: int = 30, user: dict = Depends(get_current_user)):
    if not clients.get_client(client_id, user["user_id"]):
        raise HTTPException(404, "client not found")
    return integration_settings.client_recent_tickets(client_id, user["user_id"], days=days)
