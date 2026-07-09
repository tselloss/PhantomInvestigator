"""Per-client integration credential overrides. Same shape as
routes/settings.py's global Integrations page, scoped under a client so a
client running their own Jira/GitHub/cloud account can have their
deployments' investigations authenticate against it instead of the user's
own global default. Split out from routes/clients.py the same way
routes/diagnostics.py and routes/checkin.py are: a distinct sub-domain with
its own storage module (settings.py / integration_credentials.py), just
nested under /clients/{client_id} instead of top-level."""
from fastapi import APIRouter, Depends, HTTPException

import clients
import settings as integration_settings
from routes.auth import get_current_user

router = APIRouter(prefix="/clients/{client_id}/integrations")


def _require_client(client_id: int, user_id: int) -> None:
    if not clients.get_client(client_id, user_id):
        raise HTTPException(404, "client not found")


@router.get("")
def list_client_integrations(client_id: int, user: dict = Depends(get_current_user)):
    _require_client(client_id, user["user_id"])
    return integration_settings.client_integration_status(client_id, user["user_id"])


@router.post("/{name}/test")
def test_client_integration(client_id: int, name: str, user: dict = Depends(get_current_user)):
    _require_client(client_id, user["user_id"])
    if name not in integration_settings.INTEGRATIONS:
        raise HTTPException(404, f"unknown integration '{name}'")
    return integration_settings.test_client_integration(client_id, user["user_id"], name)


@router.post("/{name}")
def set_client_integration(client_id: int, name: str, fields: dict[str, str], user: dict = Depends(get_current_user)):
    _require_client(client_id, user["user_id"])
    try:
        return integration_settings.set_client_integration(client_id, user["user_id"], name, fields)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@router.delete("/{name}")
def clear_client_integration(client_id: int, name: str, user: dict = Depends(get_current_user)):
    _require_client(client_id, user["user_id"])
    try:
        return integration_settings.clear_client_integration(client_id, user["user_id"], name)
    except ValueError as e:
        raise HTTPException(404, str(e))
