"""Self-report webhook: a shipped deployment phones home its own version/
build manifest. Outbound-only from the client's side, so it works through
NAT/firewalls with no inbound access into the client's infrastructure."""
import hmac

from fastapi import APIRouter, HTTPException, Request

import clients

router = APIRouter(prefix="/webhooks")


@router.post("/checkin/{deployment_id}")
async def checkin(deployment_id: int, request: Request, secret: str = ""):
    deployment = clients.get_deployment_unscoped(deployment_id)
    if not deployment or not deployment["checkin_token"] or not hmac.compare_digest(secret, deployment["checkin_token"]):
        raise HTTPException(401, "invalid checkin token")

    manifest = await request.json()
    snapshot = clients.record_snapshot(
        deployment_id,
        deployment["owner_user_id"],
        source="self_report",
        app_version=manifest.get("version"),
        build_sha=manifest.get("build_sha"),
        manifest=manifest,
    )
    return {"accepted": True, "snapshot_id": snapshot["id"]}
