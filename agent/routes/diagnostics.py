"""Diagnostic bundle upload -- the evidence-ingestion path for clients whose
infrastructure the agent can't query directly. An operator/field engineer
uploads on the client's behalf; each bundle is also opportunistically mined
for a version manifest so it feeds the same deployment_snapshots ledger the
self-report checkin does."""
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

import clients
import diagnostics as store
from routes.auth import get_current_user

router = APIRouter(prefix="/diagnostics")

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # these are text excerpts, not full log archives


async def _read_text(file: UploadFile | None) -> str | None:
    if file is None:
        return None
    content = await file.read()
    return content[:MAX_UPLOAD_BYTES].decode("utf-8", errors="replace")


def _try_extract_manifest(config_excerpt: str | None) -> dict | None:
    """Best-effort: if the config excerpt is a JSON object with a 'version'
    field, treat it as a build manifest -- same shape the self-report
    checkin expects, so both paths feed the same snapshot ledger."""
    if not config_excerpt:
        return None
    try:
        manifest = json.loads(config_excerpt)
    except ValueError:
        return None
    return manifest if isinstance(manifest, dict) and "version" in manifest else None


@router.post("/upload")
async def upload_bundle(
    deployment_id: int = Form(...),
    filename: str = Form("bundle"),
    investigation_id: int | None = Form(None),
    logs_file: UploadFile | None = File(None),
    metrics_file: UploadFile | None = File(None),
    config_file: UploadFile | None = File(None),
    user: dict = Depends(get_current_user),
):
    if not clients.get_deployment(deployment_id, user["user_id"]):
        raise HTTPException(404, "deployment not found")

    logs_excerpt = await _read_text(logs_file)
    metrics_excerpt = await _read_text(metrics_file)
    config_excerpt = await _read_text(config_file)
    manifest = _try_extract_manifest(config_excerpt)

    bundle = store.store_bundle(
        deployment_id,
        user["user_id"],
        filename,
        investigation_id=investigation_id,
        logs_excerpt=logs_excerpt,
        metrics_excerpt=metrics_excerpt,
        config_excerpt=config_excerpt,
        extracted_manifest=manifest,
    )

    if manifest:
        clients.record_snapshot(
            deployment_id,
            user["user_id"],
            source="diagnostic_bundle",
            app_version=manifest.get("version"),
            build_sha=manifest.get("build_sha"),
            manifest=manifest,
        )

    return bundle


@router.get("/{deployment_id}")
def get_bundles_for_deployment(deployment_id: int, user: dict = Depends(get_current_user)):
    if not clients.get_deployment(deployment_id, user["user_id"]):
        raise HTTPException(404, "deployment not found")
    return store.list_bundles(deployment_id, user["user_id"])
