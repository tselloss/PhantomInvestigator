"""Integration status/test endpoints for the Settings page."""
from fastapi import APIRouter, HTTPException

import settings as integration_settings

router = APIRouter(prefix="/settings")


@router.get("/integrations")
def list_integrations():
    return integration_settings.list_integrations()


@router.post("/integrations/{name}/test")
def test_integration(name: str):
    if name not in integration_settings.INTEGRATIONS:
        raise HTTPException(404, f"unknown integration '{name}'")
    return integration_settings.test_integration(name)
