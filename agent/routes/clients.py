"""Client/deployment registry API for the operator UI -- lets support/eng
record which clients exist, which instances they run, and (from later
slices) what's known about each instance's version and drift."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import clients as store
import investigations
from routes.auth import get_current_user

router = APIRouter(prefix="/clients")

# Declared before /{client_id} below so the literal path "deployments" isn't
# shadowed -- same reasoning as investigations.py's /stats route.


class ClientCreate(BaseModel):
    name: str
    slug: str
    notes: str | None = None


class ClientUpdate(BaseModel):
    name: str
    notes: str | None = None


class DeploymentCreate(BaseModel):
    label: str
    environment: str = "production"
    jira_project_key: str | None = None
    github_repo: str | None = None


class DeploymentUpdate(BaseModel):
    label: str
    environment: str = "production"
    jira_project_key: str | None = None
    github_repo: str | None = None


@router.get("")
def list_clients(include_archived: bool = False, user: dict = Depends(get_current_user)):
    return store.list_clients(user["user_id"], include_archived=include_archived)


@router.post("")
def create_client(body: ClientCreate, user: dict = Depends(get_current_user)):
    return store.create_client(user["user_id"], body.name, body.slug, body.notes)


@router.get("/deployments")
def list_all_deployments(include_archived: bool = False, user: dict = Depends(get_current_user)):
    """Flat list across all clients, for pickers (e.g. the Investigate page)
    that need to resolve a deployment without drilling into each client.
    Archiving a client doesn't itself archive its deployments, so an archived
    deployment's own archived_at isn't enough -- also exclude deployments
    whose parent client is archived, unless include_archived is set."""
    all_clients = {c["id"]: c for c in store.list_clients(user["user_id"], include_archived=True)}
    deployments = store.list_deployments(user["user_id"], include_archived=include_archived)
    if not include_archived:
        deployments = [d for d in deployments if not (all_clients.get(d["client_id"]) or {}).get("archived_at")]
    return [{**d, "client_name": (all_clients.get(d["client_id"]) or {}).get("name", "?")} for d in deployments]


@router.get("/{client_id}")
def get_client(client_id: int, include_archived: bool = False, user: dict = Depends(get_current_user)):
    client = store.get_client(client_id, user["user_id"])
    if not client:
        raise HTTPException(404, "client not found")
    return {
        **client,
        "deployments": store.list_deployments(user["user_id"], client_id=client_id, include_archived=include_archived),
    }


@router.patch("/{client_id}")
def update_client(client_id: int, body: ClientUpdate, user: dict = Depends(get_current_user)):
    client = store.update_client(client_id, user["user_id"], body.name, body.notes)
    if not client:
        raise HTTPException(404, "client not found")
    return client


@router.delete("/{client_id}")
def archive_client(client_id: int, user: dict = Depends(get_current_user)):
    client = store.archive_client(client_id, user["user_id"])
    if not client:
        raise HTTPException(404, "client not found")
    return client


@router.post("/{client_id}/deployments")
def create_deployment(client_id: int, body: DeploymentCreate, user: dict = Depends(get_current_user)):
    if not store.get_client(client_id, user["user_id"]):
        raise HTTPException(404, "client not found")
    return store.create_deployment(
        client_id, user["user_id"], body.label, body.environment, body.jira_project_key, body.github_repo
    )


@router.get("/{client_id}/deployments/{deployment_id}")
def get_deployment_detail(client_id: int, deployment_id: int, user: dict = Depends(get_current_user)):
    deployment = store.get_deployment(deployment_id, user["user_id"])
    if not deployment or deployment["client_id"] != client_id:
        raise HTTPException(404, "deployment not found")
    return {
        **deployment,
        "latest_snapshot": store.get_latest_snapshot(deployment_id, user["user_id"]),
        "recent_investigations": investigations.list_recent(user["user_id"], limit=10, deployment_id=deployment_id),
    }


@router.patch("/{client_id}/deployments/{deployment_id}")
def update_deployment(client_id: int, deployment_id: int, body: DeploymentUpdate, user: dict = Depends(get_current_user)):
    existing = store.get_deployment(deployment_id, user["user_id"])
    if not existing or existing["client_id"] != client_id:
        raise HTTPException(404, "deployment not found")
    return store.update_deployment(
        deployment_id, user["user_id"], body.label, body.environment, body.jira_project_key, body.github_repo
    )


@router.delete("/{client_id}/deployments/{deployment_id}")
def archive_deployment(client_id: int, deployment_id: int, user: dict = Depends(get_current_user)):
    existing = store.get_deployment(deployment_id, user["user_id"])
    if not existing or existing["client_id"] != client_id:
        raise HTTPException(404, "deployment not found")
    return store.archive_deployment(deployment_id, user["user_id"])
