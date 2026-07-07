"""Query and comment on Jira Cloud tickets via REST API v3.
Truncated so a large ticket/comment thread can't blow the context window."""
import os

import httpx

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")


def _auth():
    return (JIRA_EMAIL, JIRA_API_TOKEN)


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


def get_ticket(key: str) -> str:
    if not JIRA_BASE_URL:
        return "ERROR: JIRA_BASE_URL not configured"
    try:
        resp = httpx.get(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{key}",
            auth=_auth(),
            params={"fields": "summary,description,comment,status,created"},
            timeout=10.0,
        )
        resp.raise_for_status()
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


def post_comment(key: str, body: str) -> str:
    if not JIRA_BASE_URL:
        return "ERROR: JIRA_BASE_URL not configured"
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}],
        }
    }
    try:
        resp = httpx.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{key}/comment",
            auth=_auth(),
            json=payload,
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"ERROR posting comment to {key}: {e}"
    return f"Comment posted to {key}"
