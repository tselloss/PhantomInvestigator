"""Query and comment on Azure Boards work items (User Stories/Tasks/Bugs) via
the Azure DevOps REST API. Distinct from tools/azure_monitor.py -- that's
Azure Monitor (AAD service principal, logs/metrics); this is Azure DevOps
(personal access token, work items), a different product with different auth.
Truncated so a large description/comment thread can't blow the context window."""
import os
import re

import httpx

import integration_credentials
from ._http import request_with_retry

AZURE_DEVOPS_ORG = os.environ.get("AZURE_DEVOPS_ORG", "")
AZURE_DEVOPS_PROJECT = os.environ.get("AZURE_DEVOPS_PROJECT", "")
AZURE_DEVOPS_PAT = os.environ.get("AZURE_DEVOPS_PAT", "")

API_VERSION = "7.1"


def _config(user_id: int, deployment_id: int | None = None, client_id: int | None = None) -> dict:
    """.env defaults above, overridden field-by-field by whatever's stored
    via the Integrations page (global) or a client's own override -- see
    integration_credentials.resolve_credentials. Read fresh on every call
    (not cached at import time) so edits there take effect without a
    restart."""
    override = integration_credentials.resolve_credentials(
        "azure_devops", user_id, deployment_id=deployment_id, client_id=client_id
    ) or {}
    return {
        "organization": override.get("organization") or AZURE_DEVOPS_ORG,
        "project": override.get("project") or AZURE_DEVOPS_PROJECT,
        "pat": override.get("pat") or AZURE_DEVOPS_PAT,
    }


def _base_url(cfg: dict) -> str:
    return f"https://dev.azure.com/{cfg['organization']}/{cfg['project']}/_apis/wit"


def _strip_html(html: str | None) -> str:
    """Work item descriptions/repro steps are HTML, not plain text -- strip
    tags with a simple regex rather than pulling in an HTML parser dependency
    for this one field (mirrors jira.py's hand-walked ADF extraction in
    spirit: good enough for giving the model readable text, not a full
    renderer)."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def get_work_item(work_item_id: int, user_id: int, deployment_id: int | None = None) -> str:
    cfg = _config(user_id, deployment_id=deployment_id)
    if not (cfg["organization"] and cfg["project"] and cfg["pat"]):
        return "ERROR: Azure DevOps organization/project/PAT not configured"

    try:
        resp = request_with_retry(
            "GET",
            f"{_base_url(cfg)}/workitems/{work_item_id}",
            params={"$expand": "all", "api-version": API_VERSION},
            auth=("", cfg["pat"]),
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        return f"ERROR fetching Azure DevOps work item {work_item_id}: {e}"

    fields = resp.json().get("fields", {})
    description = fields.get("System.Description") or fields.get("Microsoft.VSTS.TCM.ReproSteps")
    lines = [
        f"Work item: {work_item_id}",
        f"Type: {fields.get('System.WorkItemType', '')}",
        f"State: {fields.get('System.State', '')}",
        f"Created: {fields.get('System.CreatedDate', '')}",
        f"Title: {fields.get('System.Title', '')}",
        f"Description: {_strip_html(description)}",
    ]

    try:
        comments_resp = request_with_retry(
            "GET",
            f"{_base_url(cfg)}/workItems/{work_item_id}/comments",
            params={"api-version": f"{API_VERSION}-preview.3"},
            auth=("", cfg["pat"]),
            timeout=10.0,
        )
        comments = [c.get("text", "") for c in comments_resp.json().get("comments", [])]
    except httpx.HTTPError:
        comments = []  # comments are supplementary -- don't fail the whole lookup if this call errors

    if comments:
        lines.append("Recent comments:")
        lines.extend(f"- {_strip_html(c)}" for c in comments[-5:])
    return "\n".join(lines)[:3000]


def post_comment(work_item_id: int, body: str, user_id: int, deployment_id: int | None = None) -> str:
    cfg = _config(user_id, deployment_id=deployment_id)
    if not (cfg["organization"] and cfg["project"] and cfg["pat"]):
        return "ERROR: Azure DevOps organization/project/PAT not configured"
    try:
        request_with_retry(
            "POST",
            f"{_base_url(cfg)}/workItems/{work_item_id}/comments",
            params={"api-version": f"{API_VERSION}-preview.3"},
            auth=("", cfg["pat"]),
            json={"text": body},
            timeout=10.0,
        )
    except httpx.HTTPError as e:
        return f"ERROR posting comment to work item {work_item_id}: {e}"
    return f"Comment posted to work item {work_item_id}"
