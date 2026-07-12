"""Query and comment on Azure Boards work items (User Stories/Tasks/Bugs) via
the Azure DevOps REST API. Distinct from tools/azure_monitor.py -- that's
Azure Monitor (AAD service principal, logs/metrics); this is Azure DevOps
(personal access token, work items), a different product with different auth.
Truncated so a large description/comment thread can't blow the context window."""
import os
import re
from datetime import datetime, timedelta, timezone

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


def _apis_url(cfg: dict) -> str:
    return f"https://dev.azure.com/{cfg['organization']}/{cfg['project']}/_apis"


def _parse_json(resp: httpx.Response, action: str) -> dict:
    """A bad or expired PAT (or one missing a required scope) makes ADO
    return HTTP 200/203 with an HTML sign-in page instead of a 401 -- detect
    that here so callers raise a clear error instead of a JSON-parse crash."""
    if "application/json" not in resp.headers.get("content-type", ""):
        raise ValueError(f"Azure DevOps PAT expired or missing required scopes ({action})")
    return resp.json()


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


def get_recent_commits(user_id: int, deployment_id: int | None = None, days: int = 7) -> str:
    """"What shipped" -- lists repos in the project, then fans out to each
    repo's recent commit history. Capped to the 10 most recently listed
    repos and 30 total commits so a large org can't turn one call into
    dozens of requests."""
    cfg = _config(user_id, deployment_id=deployment_id)
    if not (cfg["organization"] and cfg["project"] and cfg["pat"]):
        return "ERROR: Azure DevOps organization/project/PAT not configured"

    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        repos_resp = request_with_retry(
            "GET", f"{_apis_url(cfg)}/git/repositories",
            params={"api-version": API_VERSION}, auth=("", cfg["pat"]), timeout=10.0,
        )
        repos = _parse_json(repos_resp, "listing repositories").get("value", [])[:10]
    except (httpx.HTTPError, ValueError) as e:
        return f"ERROR listing Azure DevOps repositories: {e}"

    if not repos:
        return "No repositories found."

    lines = []
    for repo in repos:
        try:
            commits_resp = request_with_retry(
                "GET", f"{_apis_url(cfg)}/git/repositories/{repo['id']}/commits",
                params={"searchCriteria.fromDate": since, "api-version": API_VERSION},
                auth=("", cfg["pat"]), timeout=10.0,
            )
            commits = _parse_json(commits_resp, f"listing commits for {repo['name']}").get("value", [])
        except ValueError as e:
            return f"ERROR: {e}"
        except httpx.HTTPError:
            continue  # one repo failing (e.g. disabled/empty) shouldn't block the rest
        for c in commits:
            comment = (c.get("comment") or "").splitlines()[0] if c.get("comment") else ""
            lines.append(
                f"- {repo['name']} {c['commitId'][:7]} | {c.get('author', {}).get('name', 'unknown')} | "
                f"{c.get('author', {}).get('date', '')} | {comment}"
            )
    if not lines:
        return f"No commits in the last {days} day(s)."
    return "\n".join(lines[:30])[:4000]


def get_recent_builds(user_id: int, deployment_id: int | None = None, hours: int = 24, failed_only: bool = False) -> str:
    """The money query during an incident: what built recently and did it
    fail. Capped to the 20 most recent builds in the window."""
    cfg = _config(user_id, deployment_id=deployment_id)
    if not (cfg["organization"] and cfg["project"] and cfg["pat"]):
        return "ERROR: Azure DevOps organization/project/PAT not configured"

    min_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {"minTime": min_time, "api-version": API_VERSION, "$top": 20}
    if failed_only:
        params["resultFilter"] = "failed"
    try:
        resp = request_with_retry(
            "GET", f"{_apis_url(cfg)}/build/builds", params=params, auth=("", cfg["pat"]), timeout=10.0,
        )
        builds = _parse_json(resp, "listing builds").get("value", [])
    except (httpx.HTTPError, ValueError) as e:
        return f"ERROR listing Azure DevOps builds: {e}"

    if not builds:
        suffix = " (failed only)" if failed_only else ""
        return f"No builds in the last {hours} hour(s){suffix}."

    lines = [
        f"- build {b['id']} | {b.get('definition', {}).get('name', '')} | {b.get('status', '')}/"
        f"{b.get('result', '')} | branch={b.get('sourceBranch', '')} | sha={b.get('sourceVersion', '')[:7]} | "
        f"{b.get('startTime', '')}"
        for b in builds
    ]
    return "\n".join(lines)[:4000]


def _wiql_items(cfg: dict, wiql: str) -> list[dict]:
    """Runs a WIQL query and batch-fetches full field data for every matching
    work item id (capped to 20). Shared by search_work_items (agent tool,
    title-filtered) and list_recent_work_items (Clients page browse view,
    unfiltered) -- both need the same two-step WIQL-then-batch-fetch dance,
    just with a different WHERE clause. Raises (httpx.HTTPError, ValueError)
    same as the individual requests -- callers decide how to present that."""
    wiql_resp = request_with_retry(
        "POST", f"{_apis_url(cfg)}/wit/wiql",
        params={"api-version": API_VERSION}, auth=("", cfg["pat"]), json={"query": wiql}, timeout=10.0,
    )
    ids = [str(item["id"]) for item in _parse_json(wiql_resp, "searching work items").get("workItems", [])][:20]
    if not ids:
        return []
    items_resp = request_with_retry(
        "GET", f"{_apis_url(cfg)}/wit/workitems",
        params={
            "ids": ",".join(ids),
            "fields": "System.Id,System.Title,System.WorkItemType,System.State,System.ChangedDate",
            "api-version": API_VERSION,
        },
        auth=("", cfg["pat"]), timeout=10.0,
    )
    return _parse_json(items_resp, "fetching work item details").get("value", [])


def search_work_items(query: str, user_id: int, deployment_id: int | None = None, days: int = 7) -> str:
    """WIQL search over work items changed in the last N days whose title
    matches query -- the Azure Boards equivalent of a Jira JQL search, for
    when no specific work item id is known."""
    if not query.strip():
        return "ERROR: query must not be empty"

    cfg = _config(user_id, deployment_id=deployment_id)
    if not (cfg["organization"] and cfg["project"] and cfg["pat"]):
        return "ERROR: Azure DevOps organization/project/PAT not configured"

    escaped = query.replace("'", "''")  # WIQL string literal, not user input trusted verbatim
    wiql = (
        "SELECT [System.Id] FROM WorkItems "
        f"WHERE [System.ChangedDate] >= @Today - {int(days)} "
        f"AND [System.Title] CONTAINS WORDS '{escaped}' "
        "ORDER BY [System.ChangedDate] DESC"
    )
    try:
        items = _wiql_items(cfg, wiql)
    except (httpx.HTTPError, ValueError) as e:
        return f"ERROR searching Azure DevOps work items: {e}"

    if not items:
        return f"No work items matching '{query}' changed in the last {days} day(s)."

    lines = [
        f"- #{i['fields']['System.Id']} [{i['fields'].get('System.WorkItemType', '')}] "
        f"{i['fields'].get('System.Title', '')} ({i['fields'].get('System.State', '')}, "
        f"changed {i['fields'].get('System.ChangedDate', '')})"
        for i in items
    ]
    return "\n".join(lines)[:4000]


def list_recent_work_items(user_id: int, client_id: int | None = None, days: int = 30) -> list[dict]:
    """Recently changed work items, most-recent first -- powers the Clients
    page's aggregated "Bugs & tasks" view. Unlike search_work_items, no title
    filter -- this is a browse view, not an agent-driven text search, so
    no-config/failures just return an empty list rather than an ERROR string."""
    cfg = _config(user_id, client_id=client_id)
    if not (cfg["organization"] and cfg["project"] and cfg["pat"]):
        return []

    wiql = (
        "SELECT [System.Id] FROM WorkItems "
        f"WHERE [System.ChangedDate] >= @Today - {int(days)} "
        "ORDER BY [System.ChangedDate] DESC"
    )
    try:
        items = _wiql_items(cfg, wiql)
    except (httpx.HTTPError, ValueError):
        return []

    return [
        {
            "source": "azure_devops",
            "id": i["fields"]["System.Id"],
            "title": i["fields"].get("System.Title", ""),
            "type": i["fields"].get("System.WorkItemType", ""),
            "status": i["fields"].get("System.State", ""),
            "updated": i["fields"].get("System.ChangedDate", ""),
            "url": f"https://dev.azure.com/{cfg['organization']}/{cfg['project']}/_workitems/edit/{i['fields']['System.Id']}",
        }
        for i in items
    ]
