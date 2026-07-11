"""Search Zendesk support tickets via the real Search API. Lets the agent
correlate customer-reported impact (support tickets) with engineering
signals (Jira/GitHub/metrics/logs) -- a real incident often shows up in
both places, and the timing/volume of tickets is evidence engineering
tools alone don't have. Read-only: no post_comment/write path, unlike
jira.py/azure_devops.py -- support tickets aren't a place this agent
posts back to."""
import os

import httpx

import demo_data
import integration_credentials
import users
from ._http import request_with_retry

ZENDESK_SUBDOMAIN = os.environ.get("ZENDESK_SUBDOMAIN", "")
ZENDESK_EMAIL = os.environ.get("ZENDESK_EMAIL", "")
ZENDESK_API_TOKEN = os.environ.get("ZENDESK_API_TOKEN", "")


def _config(user_id: int, deployment_id: int | None = None, client_id: int | None = None) -> dict:
    """.env defaults above, overridden field-by-field by whatever's stored
    via the Integrations page (global) or a client's own override -- see
    integration_credentials.resolve_credentials. Read fresh on every call
    (not cached at import time) so edits there take effect without a
    restart."""
    override = integration_credentials.resolve_credentials(
        "zendesk", user_id, deployment_id=deployment_id, client_id=client_id
    ) or {}
    return {
        "subdomain": override.get("subdomain") or ZENDESK_SUBDOMAIN,
        "email": override.get("email") or ZENDESK_EMAIL,
        "api_token": override.get("api_token") or ZENDESK_API_TOKEN,
    }


def _base_url(cfg: dict) -> str:
    return f"https://{cfg['subdomain']}.zendesk.com/api/v2"


def _auth(cfg: dict) -> tuple[str, str]:
    # Zendesk's token-auth convention: username is "{email}/token", password
    # is the API token itself -- not the account password.
    return (f"{cfg['email']}/token", cfg["api_token"])


def search_tickets(query: str, user_id: int, deployment_id: int | None = None) -> str:
    """query: free-text search terms, combined with type:ticket server-side
    so this can't accidentally search users/organizations instead."""
    cfg = _config(user_id, deployment_id=deployment_id)
    if not (cfg["subdomain"] and cfg["email"] and cfg["api_token"]):
        if users.get_demo_mode(user_id):
            return demo_data.zendesk_tickets(query)
        return "ERROR: Zendesk subdomain/email/API token not configured"
    try:
        resp = request_with_retry(
            "GET",
            f"{_base_url(cfg)}/search.json",
            auth=_auth(cfg),
            params={"query": f"type:ticket {query}"},
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        return f"ERROR searching Zendesk tickets: {e}"

    results = resp.json().get("results", [])
    if not results:
        return "No matching support tickets found."
    lines = [
        f"- #{t.get('id')} [{t.get('status')}] {t.get('subject')} "
        f"(created {t.get('created_at')}): {(t.get('description') or '')[:200]}"
        for t in results[:10]
    ]
    return "\n".join(lines)[:3000]
