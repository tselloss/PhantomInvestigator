"""Integration status/test/credential endpoints for the Settings page.
Literal-path routes (integrations, integrations/fields) are declared before
the {name} routes so they aren't shadowed -- same reasoning as
investigations.py's /stats route."""
from fastapi import APIRouter, Depends, HTTPException

import settings as integration_settings
from routes.auth import get_current_user

router = APIRouter(prefix="/settings")


@router.get("/integrations")
def list_integrations(user: dict = Depends(get_current_user)):
    return integration_settings.list_integrations(user["user_id"])


@router.get("/integrations/fields")
def integration_fields():
    """Field schema (keys/labels/secret flags only, never values) so the
    frontend can render an edit form per integration without duplicating
    this list."""
    return integration_settings.EDITABLE_FIELDS


@router.post("/integrations/{name}/test")
def test_integration(name: str, user: dict = Depends(get_current_user)):
    if name not in integration_settings.INTEGRATIONS:
        raise HTTPException(404, f"unknown integration '{name}'")
    return integration_settings.test_integration(user["user_id"], name)


@router.post("/integrations/{name}")
def set_integration(name: str, fields: dict[str, str], user: dict = Depends(get_current_user)):
    try:
        return integration_settings.set_integration(user["user_id"], name, fields)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@router.delete("/integrations/{name}")
def clear_integration(name: str, user: dict = Depends(get_current_user)):
    try:
        return integration_settings.clear_integration(user["user_id"], name)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/ai")
def get_ai_provider(user: dict = Depends(get_current_user)):
    return integration_settings.get_ai_provider_status(user["user_id"])


@router.get("/ai/fields")
def ai_provider_fields():
    return integration_settings.AI_FIELDS


@router.post("/ai")
def set_ai_provider(fields: dict[str, str], user: dict = Depends(get_current_user)):
    try:
        return integration_settings.set_ai_provider(user["user_id"], fields)
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@router.delete("/ai")
def clear_ai_provider(user: dict = Depends(get_current_user)):
    return integration_settings.clear_ai_provider(user["user_id"])


@router.post("/ai/test")
def test_ai_provider(user: dict = Depends(get_current_user)):
    return integration_settings.test_ai_provider(user["user_id"])
