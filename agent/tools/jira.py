"""Query and comment on Jira Cloud tickets via REST API v3.
Truncated so a large ticket/comment thread can't blow the context window."""
import os

import httpx

import integration_credentials
from ._http import request_with_retry

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")


def _config(user_id: int, deployment_id: int | None = None, client_id: int | None = None) -> dict:
    """.env defaults above, overridden field-by-field by whatever's stored
    via the Integrations page (global) or, if deployment_id/client_id
    resolves to one, a client's own override -- see
    integration_credentials.resolve_credentials. Read fresh on every call
    (not cached at import time) so edits there take effect without a
    restart."""
    override = integration_credentials.resolve_credentials(
        "jira", user_id, deployment_id=deployment_id, client_id=client_id
    ) or {}
    return {
        "base_url": override.get("base_url") or JIRA_BASE_URL,
        "email": override.get("email") or JIRA_EMAIL,
        "api_token": override.get("api_token") or JIRA_API_TOKEN,
    }


def _extract_text(adf) -> str:
    """Jira descriptions/comments are Atlassian Document Format (ADF), not
    plain text. Walk the node tree and join all 'text' leaves."""
    if not adf:
        return ""
    if isinstance(adf, str):
        return adf
    texts = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                texts.append(node.get("text", ""))
            for child in node.get("content", []):
                walk(child)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(adf)
    return " ".join(texts)


def issue_url(key: str, user_id: int, deployment_id: int | None = None) -> str | None:
    """Browser-facing link for a ticket, resolved with the same per-deployment/
    per-user override precedence as every other Jira call -- None when no
    base_url is configured at all, so callers can omit the link instead of
    rendering one that 404s."""
    base_url = _config(user_id, deployment_id=deployment_id)["base_url"]
    return f"{base_url}/browse/{key}" if base_url else None


def get_ticket(key: str, user_id: int, deployment_id: int | None = None) -> str:
    cfg = _config(user_id, deployment_id=deployment_id)
    if not cfg["base_url"]:
        return "ERROR: JIRA_BASE_URL not configured"
    try:
        resp = request_with_retry(
            "GET",
            f"{cfg['base_url']}/rest/api/3/issue/{key}",
            auth=(cfg["email"], cfg["api_token"]),
            params={"fields": "summary,description,comment,status,created"},
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        return f"ERROR fetching Jira ticket {key}: {e}"

    fields = resp.json().get("fields", {})
    comments = [
        _extract_text(c.get("body"))
        for c in fields.get("comment", {}).get("comments", [])
    ]
    lines = [
        f"Key: {key}",
        f"Status: {fields.get('status', {}).get('name', '')}",
        f"Created: {fields.get('created', '')}",
        f"Summary: {fields.get('summary', '')}",
        f"Description: {_extract_text(fields.get('description'))}",
    ]
    if comments:
        lines.append("Recent comments:")
        lines.extend(f"- {c}" for c in comments[-5:])
    return "\n".join(lines)[:3000]


def list_recent_issues(user_id: int, client_id: int | None = None, days: int = 30) -> list[dict]:
    """Recently created issues visible to this account, most-recent first --
    powers the Clients page's aggregated "Bugs & tasks" view. Unlike
    get_ticket, this is a browse view, not investigation evidence, so
    no-config/failures just return an empty list rather than an ERROR string."""
    cfg = _config(user_id, client_id=client_id)
    if not cfg["base_url"]:
        return []
    try:
        resp = request_with_retry(
            "GET",
            f"{cfg['base_url']}/rest/api/3/search",
            auth=(cfg["email"], cfg["api_token"]),
            params={
                "jql": f"created >= -{int(days)}d ORDER BY created DESC",
                "fields": "summary,status,created,issuetype",
                "maxResults": 20,
            },
            timeout=10.0,
        )
    except httpx.HTTPError:
        return []
    issues = resp.json().get("issues", [])
    return [
        {
            "source": "jira",
            "id": i["key"],
            "title": i["fields"].get("summary", ""),
            "type": i["fields"].get("issuetype", {}).get("name", ""),
            "status": i["fields"].get("status", {}).get("name", ""),
            "updated": i["fields"].get("created", ""),
            "url": f"{cfg['base_url']}/browse/{i['key']}",
        }
        for i in issues
    ]


def post_comment(key: str, body: str, user_id: int, deployment_id: int | None = None) -> str:
    cfg = _config(user_id, deployment_id=deployment_id)
    if not cfg["base_url"]:
        return "ERROR: JIRA_BASE_URL not configured"
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}],
        }
    }
    try:
        request_with_retry(
            "POST",
            f"{cfg['base_url']}/rest/api/3/issue/{key}/comment",
            auth=(cfg["email"], cfg["api_token"]),
            json=payload,
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        return f"ERROR posting comment to {key}: {e}"
    return f"Comment posted to {key}"
