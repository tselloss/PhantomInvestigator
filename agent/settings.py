"""Integration status/health checks for the Settings page. Reports only
presence of config (booleans) and live connection results -- never secret
values. Every function here is scoped to the logged-in user: "global" now
means "this user's own default across their clients", not a single
console-wide value."""
import os
from datetime import datetime, timezone

import httpx

import billing
import integration_credentials
import providers
import users
from tools import aws_cloudwatch, azure_devops, azure_monitor, github_actions, jira, loki, prometheus, zendesk

INTEGRATIONS = ["jira", "github", "azure", "aws", "prometheus", "loki", "azure_devops", "zendesk"]

_READY_PATH = {"prometheus": "/-/ready", "loki": "/ready"}


def _reachable(name: str, url: str) -> bool:
    """prometheus/loki have no credentials to check presence of -- just a
    URL, which always resolves to *something* (falls back to the
    docker-compose service name or localhost) whether or not that target
    actually exists. A short-timeout live check is the only way to tell
    "configured" from "still pointing at a dev-only default with nothing
    listening" (e.g. docker-compose.prod.yml doesn't run these services at
    all -- see its header comment)."""
    try:
        resp = httpx.get(f"{url}{_READY_PATH[name]}", timeout=2.0)
        resp.raise_for_status()
        return True
    except httpx.HTTPError:
        return False

# The AI provider that powers the investigation loop itself (bring-your-own-
# key) is deliberately kept out of INTEGRATIONS/EDITABLE_FIELDS above: that
# list also drives the per-client Settings UI (client_integration_status
# etc.), and this key funds this user's own usage, not one investigated
# client's -- it must stay global (per-user), not client-scoped.
AI_FIELDS = [
    {"key": "provider", "label": "Provider", "secret": False, "options": ["anthropic", "openai", "openai_compatible"]},
    {"key": "api_key", "label": "API key", "secret": True},
    {"key": "model", "label": "Model", "secret": False},
    {"key": "base_url", "label": "Base URL (openai_compatible only)", "secret": False},
]


def get_ai_provider_status(user_id: int) -> dict:
    cfg = providers.resolve_ai_config(user_id)
    return {
        "configured": bool(cfg["api_key"]),
        "provider": cfg["provider"],
        "override": integration_credentials.has_override(user_id, "ai"),
    }


def set_ai_provider(user_id: int, fields: dict) -> dict:
    allowed_keys = {f["key"] for f in AI_FIELDS}
    clean_fields = {k: v for k, v in fields.items() if k in allowed_keys and isinstance(v, str)}
    integration_credentials.set_credentials(user_id, "ai", clean_fields)
    return get_ai_provider_status(user_id)


def clear_ai_provider(user_id: int) -> dict:
    integration_credentials.clear_credentials(user_id, "ai")
    return get_ai_provider_status(user_id)


def test_ai_provider(user_id: int) -> dict:
    status = get_ai_provider_status(user_id)
    if not status["configured"]:
        return {"ok": False, "detail": "not configured"}
    try:
        providers.get_provider(user_id).test()
        return {"ok": True, "detail": f"{status['provider']} key valid"}
    except Exception as e:
        return {"ok": False, "detail": f"{type(e).__name__}: {e}"}

# Which integrations accept credentials from the UI (vs. prometheus/loki,
# which just point at the local compose services and have nothing secret to
# store), and which fields each one takes. "secret": True fields render as
# password inputs and are never echoed back once saved.
EDITABLE_FIELDS = {
    "jira": [
        {"key": "base_url", "label": "Base URL", "secret": False},
        {"key": "email", "label": "Email", "secret": False},
        {"key": "api_token", "label": "API token", "secret": True},
    ],
    "github": [
        {"key": "token", "label": "Personal access token", "secret": True},
    ],
    "azure": [
        {"key": "tenant_id", "label": "Tenant ID", "secret": False},
        {"key": "client_id", "label": "Client ID", "secret": False},
        {"key": "client_secret", "label": "Client secret", "secret": True},
        {"key": "log_analytics_workspace_id", "label": "Log Analytics workspace ID", "secret": False},
        {"key": "metrics_endpoint", "label": "Metrics endpoint", "secret": False},
    ],
    "aws": [
        {"key": "access_key_id", "label": "Access key ID", "secret": False},
        {"key": "secret_access_key", "label": "Secret access key", "secret": True},
        {"key": "region", "label": "Region", "secret": False},
    ],
    "prometheus": [
        {"key": "url", "label": "URL", "secret": False},
    ],
    "loki": [
        {"key": "url", "label": "URL", "secret": False},
    ],
    "azure_devops": [
        {"key": "organization", "label": "Organization", "secret": False},
        {"key": "project", "label": "Project", "secret": False},
        {"key": "pat", "label": "Personal access token", "secret": True},
    ],
    "zendesk": [
        {"key": "subdomain", "label": "Subdomain", "secret": False},
        {"key": "email", "label": "Email", "secret": False},
        {"key": "api_token", "label": "API token", "secret": True},
    ],
}


def _configured(user_id: int, name: str) -> bool:
    if name == "jira":
        cfg = jira._config(user_id)
        return bool(cfg["base_url"] and cfg["email"] and cfg["api_token"])
    if name == "github":
        return bool(github_actions._config(user_id)["token"])
    if name == "azure":
        cfg = azure_monitor._config(user_id)
        return bool(cfg["tenant_id"] and cfg["client_id"] and cfg["client_secret"])
    if name == "aws":
        cfg = aws_cloudwatch._config(user_id)
        return bool(cfg["access_key_id"] and cfg["secret_access_key"])
    if name == "prometheus":
        return _reachable("prometheus", prometheus._config(user_id)["url"])
    if name == "loki":
        return _reachable("loki", loki._config(user_id)["url"])
    if name == "azure_devops":
        cfg = azure_devops._config(user_id)
        return bool(cfg["organization"] and cfg["project"] and cfg["pat"])
    if name == "zendesk":
        cfg = zendesk._config(user_id)
        return bool(cfg["subdomain"] and cfg["email"] and cfg["api_token"])
    return False


def list_integrations(user_id: int) -> list[dict]:
    return [
        {
            "name": name,
            "configured": _configured(user_id, name),
            "editable": name in EDITABLE_FIELDS,
            "override": name in EDITABLE_FIELDS and integration_credentials.has_override(user_id, name),
        }
        for name in INTEGRATIONS
    ]


def set_integration(user_id: int, name: str, fields: dict) -> dict:
    """Stores an encrypted, DB-backed override for the given integration's
    credentials. Only accepts keys from that integration's EDITABLE_FIELDS
    whitelist -- anything else is silently dropped rather than stored."""
    if name not in EDITABLE_FIELDS:
        raise ValueError(f"'{name}' has no editable credential fields")
    allowed_keys = {f["key"] for f in EDITABLE_FIELDS[name]}
    clean_fields = {k: v for k, v in fields.items() if k in allowed_keys and isinstance(v, str)}
    integration_credentials.set_credentials(user_id, name, clean_fields)
    return {"name": name, "configured": _configured(user_id, name), "override": True}


def clear_integration(user_id: int, name: str) -> dict:
    if name not in EDITABLE_FIELDS:
        raise ValueError(f"'{name}' has no editable credential fields")
    integration_credentials.clear_credentials(user_id, name)
    return {"name": name, "configured": _configured(user_id, name), "override": False}


def test_integration(user_id: int, name: str) -> dict:
    if name not in INTEGRATIONS:
        return {"ok": False, "detail": f"unknown integration '{name}'"}
    if not _configured(user_id, name):
        return {"ok": False, "detail": "not configured"}

    try:
        if name == "jira":
            cfg = jira._config(user_id)
            resp = httpx.get(
                f"{cfg['base_url']}/rest/api/3/myself",
                auth=(cfg["email"], cfg["api_token"]),
                timeout=10.0,
            )
            resp.raise_for_status()
            return {"ok": True, "detail": f"authenticated as {resp.json().get('displayName', 'unknown user')}"}

        if name == "github":
            resp = httpx.get(
                "https://api.github.com/rate_limit",
                headers={"Authorization": f"Bearer {github_actions._config(user_id)['token']}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            remaining = resp.json().get("rate", {}).get("remaining")
            return {"ok": True, "detail": f"token valid, {remaining} API calls remaining this hour"}

        if name == "azure":
            token = azure_monitor._credential(user_id).get_token("https://management.azure.com/.default")
            return {"ok": bool(token.token), "detail": "service principal authenticated"}

        if name == "aws":
            identity = aws_cloudwatch._client("sts", user_id).get_caller_identity()
            return {"ok": True, "detail": f"authenticated as {identity.get('Arn', 'unknown')}"}

        if name == "prometheus":
            resp = httpx.get(f"{prometheus._config(user_id)['url']}/-/ready", timeout=10.0)
            resp.raise_for_status()
            return {"ok": True, "detail": "reachable"}

        if name == "loki":
            resp = httpx.get(f"{loki._config(user_id)['url']}/ready", timeout=10.0)
            resp.raise_for_status()
            return {"ok": True, "detail": "reachable"}

        if name == "azure_devops":
            cfg = azure_devops._config(user_id)
            resp = httpx.get(
                f"https://dev.azure.com/{cfg['organization']}/_apis/connectionData",
                # connectionData is a preview resource -- plain "7.1" 400s with
                # VssInvalidPreviewVersionException on orgs that haven't opted
                # it out of preview, unlike wit/git/build which take "7.1" as-is.
                params={"api-version": "7.1-preview.1"},
                auth=("", cfg["pat"]),
                timeout=10.0,
            )
            resp.raise_for_status()
            who = resp.json().get("authenticatedUser", {}).get("providerDisplayName", "unknown user")
            return {"ok": True, "detail": f"authenticated as {who}"}

        if name == "zendesk":
            cfg = zendesk._config(user_id)
            resp = httpx.get(
                f"{zendesk._base_url(cfg)}/users/me.json",
                auth=zendesk._auth(cfg),
                timeout=10.0,
            )
            resp.raise_for_status()
            return {"ok": True, "detail": f"authenticated as {resp.json().get('user', {}).get('name', 'unknown user')}"}
    except Exception as e:
        return {"ok": False, "detail": f"{type(e).__name__}: {e}"}

    return {"ok": False, "detail": "no test defined"}


def _client_configured(client_id: int, user_id: int, name: str) -> bool:
    """Same shape as _configured(), but layered through this client's
    override (client override -> user's own global override -> env) via each
    tool's _config(client_id=...) -- i.e. reports whether an investigation
    scoped to this client would find *some* usable config, not just whether
    this client has its own override (see client_integration_status's
    separate 'override' / 'using_global_default' flags for that
    distinction)."""
    if name == "jira":
        cfg = jira._config(user_id, client_id=client_id)
        return bool(cfg["base_url"] and cfg["email"] and cfg["api_token"])
    if name == "github":
        return bool(github_actions._config(user_id, client_id=client_id)["token"])
    if name == "azure":
        cfg = azure_monitor._config(user_id, client_id=client_id)
        return bool(cfg["tenant_id"] and cfg["client_id"] and cfg["client_secret"])
    if name == "aws":
        cfg = aws_cloudwatch._config(user_id, client_id=client_id)
        return bool(cfg["access_key_id"] and cfg["secret_access_key"])
    if name == "prometheus":
        return _reachable("prometheus", prometheus._config(user_id, client_id=client_id)["url"])
    if name == "loki":
        return _reachable("loki", loki._config(user_id, client_id=client_id)["url"])
    if name == "azure_devops":
        cfg = azure_devops._config(user_id, client_id=client_id)
        return bool(cfg["organization"] and cfg["project"] and cfg["pat"])
    if name == "zendesk":
        cfg = zendesk._config(user_id, client_id=client_id)
        return bool(cfg["subdomain"] and cfg["email"] and cfg["api_token"])
    return False


def client_integration_status(client_id: int, user_id: int) -> list[dict]:
    result = []
    for name in INTEGRATIONS:
        editable = name in EDITABLE_FIELDS
        own_override = editable and integration_credentials.has_client_override(client_id, user_id, name)
        result.append({
            "name": name,
            "configured": _client_configured(client_id, user_id, name),
            "editable": editable,
            "override": own_override,
            # Lets the UI distinguish "this client's own override" from
            # "falling through to the user's own global default" without a
            # second request.
            "using_global_default": editable and not own_override and integration_credentials.has_override(user_id, name),
        })
    return result


def _ticket_sort_key(item: dict) -> datetime:
    """Jira/Azure DevOps/Zendesk each stamp "updated" in a slightly different
    ISO 8601 flavor (with/without milliseconds, "Z" vs "+0000") -- parse
    rather than compare as raw strings, and tolerate a missing/malformed
    value instead of crashing sort()."""
    try:
        return datetime.fromisoformat(item["updated"].replace("Z", "+00:00"))
    except (ValueError, KeyError, AttributeError):
        return datetime.min.replace(tzinfo=timezone.utc)


_CLOSED_STATUS_WORDS = ("done", "closed", "resolved", "solved")


def _is_closed(item: dict) -> bool:
    status = (item.get("status") or "").lower()
    return any(word in status for word in _CLOSED_STATUS_WORDS)


def client_recent_tickets(client_id: int, user_id: int, days: int = 30) -> list[dict]:
    """Aggregated *open* bugs/tasks across Jira, Azure DevOps, and Zendesk for
    this client -- powers the Clients page's "Candidate incidents" section.
    Closed/done/resolved/solved items are filtered out: the point of this
    list is "what might still need investigating," not a full ticket
    history (Jira/Azure DevOps/Zendesk already show that natively). Each
    source resolves its own config (client override -> shared global default
    -> demo data) the same way every other per-client call does; a source
    with nothing configured just contributes no items, same as it would
    silently do for an investigation."""
    items = (
        jira.list_recent_issues(user_id, client_id=client_id, days=days)
        + azure_devops.list_recent_work_items(user_id, client_id=client_id, days=days)
        + zendesk.list_recent_tickets(user_id, client_id=client_id, days=days)
    )
    items = [item for item in items if not _is_closed(item)]
    items.sort(key=_ticket_sort_key, reverse=True)
    return items[:30]


def set_client_integration(client_id: int, user_id: int, name: str, fields: dict) -> dict:
    if name not in EDITABLE_FIELDS:
        raise ValueError(f"'{name}' has no editable credential fields")
    allowed_keys = {f["key"] for f in EDITABLE_FIELDS[name]}
    clean_fields = {k: v for k, v in fields.items() if k in allowed_keys and isinstance(v, str)}
    integration_credentials.set_client_credentials(client_id, user_id, name, clean_fields)
    return {"name": name, "configured": _client_configured(client_id, user_id, name), "override": True}


def clear_client_integration(client_id: int, user_id: int, name: str) -> dict:
    if name not in EDITABLE_FIELDS:
        raise ValueError(f"'{name}' has no editable credential fields")
    integration_credentials.clear_client_credentials(client_id, user_id, name)
    return {"name": name, "configured": _client_configured(client_id, user_id, name), "override": False}


def test_client_integration(client_id: int, user_id: int, name: str) -> dict:
    if name not in INTEGRATIONS:
        return {"ok": False, "detail": f"unknown integration '{name}'"}
    if not _client_configured(client_id, user_id, name):
        return {"ok": False, "detail": "not configured"}

    try:
        if name == "jira":
            cfg = jira._config(user_id, client_id=client_id)
            resp = httpx.get(
                f"{cfg['base_url']}/rest/api/3/myself",
                auth=(cfg["email"], cfg["api_token"]),
                timeout=10.0,
            )
            resp.raise_for_status()
            return {"ok": True, "detail": f"authenticated as {resp.json().get('displayName', 'unknown user')}"}

        if name == "github":
            resp = httpx.get(
                "https://api.github.com/rate_limit",
                headers={"Authorization": f"Bearer {github_actions._config(user_id, client_id=client_id)['token']}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            remaining = resp.json().get("rate", {}).get("remaining")
            return {"ok": True, "detail": f"token valid, {remaining} API calls remaining this hour"}

        if name == "azure":
            token = azure_monitor._credential(user_id, client_id=client_id).get_token("https://management.azure.com/.default")
            return {"ok": bool(token.token), "detail": "service principal authenticated"}

        if name == "aws":
            identity = aws_cloudwatch._client("sts", user_id, client_id=client_id).get_caller_identity()
            return {"ok": True, "detail": f"authenticated as {identity.get('Arn', 'unknown')}"}

        if name == "prometheus":
            resp = httpx.get(f"{prometheus._config(user_id, client_id=client_id)['url']}/-/ready", timeout=10.0)
            resp.raise_for_status()
            return {"ok": True, "detail": "reachable"}

        if name == "loki":
            resp = httpx.get(f"{loki._config(user_id, client_id=client_id)['url']}/ready", timeout=10.0)
            resp.raise_for_status()
            return {"ok": True, "detail": "reachable"}

        if name == "azure_devops":
            cfg = azure_devops._config(user_id, client_id=client_id)
            resp = httpx.get(
                f"https://dev.azure.com/{cfg['organization']}/_apis/connectionData",
                params={"api-version": "7.1-preview.1"},
                auth=("", cfg["pat"]),
                timeout=10.0,
            )
            resp.raise_for_status()
            who = resp.json().get("authenticatedUser", {}).get("providerDisplayName", "unknown user")
            return {"ok": True, "detail": f"authenticated as {who}"}

        if name == "zendesk":
            cfg = zendesk._config(user_id, client_id=client_id)
            resp = httpx.get(
                f"{zendesk._base_url(cfg)}/users/me.json",
                auth=zendesk._auth(cfg),
                timeout=10.0,
            )
            resp.raise_for_status()
            return {"ok": True, "detail": f"authenticated as {resp.json().get('user', {}).get('name', 'unknown user')}"}
    except Exception as e:
        return {"ok": False, "detail": f"{type(e).__name__}: {e}"}

    return {"ok": False, "detail": "no test defined"}


def get_profile(user_id: int) -> dict:
    user = users.get_user_by_id(user_id)
    budget = billing.check_budget(user_id)
    return {
        "username": user["username"],
        "email": user.get("email"),
        "sign_in_method": "google" if user.get("google_id") else "password",
        "monthly_limit_usd": budget["limit_usd"],
        "spent_this_month_usd": budget["spent_usd"],
        "demo_mode": bool(user.get("demo_mode")),
    }


def set_monthly_limit(user_id: int, limit_usd: float | None) -> dict:
    if limit_usd is not None and limit_usd < 0:
        raise ValueError("monthly_limit_usd must be >= 0")
    users.update_monthly_limit(user_id, limit_usd)
    return get_profile(user_id)


def set_demo_mode(user_id: int, enabled: bool) -> dict:
    users.update_demo_mode(user_id, enabled)
    return get_profile(user_id)
