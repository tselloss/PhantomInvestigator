"""Integration status/health checks for the Settings page. Reports only
presence of config (booleans) and live connection results -- never secret
values."""
import os

import httpx

from tools import aws_cloudwatch, azure_monitor, github_actions, jira, loki, prometheus

INTEGRATIONS = ["jira", "github", "azure", "aws", "prometheus", "loki"]


def _configured(name: str) -> bool:
    if name == "jira":
        return bool(jira.JIRA_BASE_URL and jira.JIRA_EMAIL and jira.JIRA_API_TOKEN)
    if name == "github":
        return bool(github_actions.GITHUB_TOKEN)
    if name == "azure":
        return bool(
            azure_monitor.AZURE_TENANT_ID and azure_monitor.AZURE_CLIENT_ID and azure_monitor.AZURE_CLIENT_SECRET
        )
    if name == "aws":
        return bool(aws_cloudwatch.AWS_ACCESS_KEY_ID and aws_cloudwatch.AWS_SECRET_ACCESS_KEY)
    if name in ("prometheus", "loki"):
        return True  # always has a default URL, pointed at the local compose service
    return False


def list_integrations() -> list[dict]:
    return [{"name": name, "configured": _configured(name)} for name in INTEGRATIONS]


def test_integration(name: str) -> dict:
    if name not in INTEGRATIONS:
        return {"ok": False, "detail": f"unknown integration '{name}'"}
    if not _configured(name):
        return {"ok": False, "detail": "not configured"}

    try:
        if name == "jira":
            resp = httpx.get(
                f"{jira.JIRA_BASE_URL}/rest/api/3/myself",
                auth=(jira.JIRA_EMAIL, jira.JIRA_API_TOKEN),
                timeout=10.0,
            )
            resp.raise_for_status()
            return {"ok": True, "detail": f"authenticated as {resp.json().get('displayName', 'unknown user')}"}

        if name == "github":
            resp = httpx.get(
                "https://api.github.com/rate_limit",
                headers={"Authorization": f"Bearer {github_actions.GITHUB_TOKEN}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            remaining = resp.json().get("rate", {}).get("remaining")
            return {"ok": True, "detail": f"token valid, {remaining} API calls remaining this hour"}

        if name == "azure":
            token = azure_monitor._credential().get_token("https://management.azure.com/.default")
            return {"ok": bool(token.token), "detail": "service principal authenticated"}

        if name == "aws":
            identity = aws_cloudwatch._client("sts").get_caller_identity()
            return {"ok": True, "detail": f"authenticated as {identity.get('Arn', 'unknown')}"}

        if name == "prometheus":
            resp = httpx.get(f"{prometheus.PROMETHEUS_URL}/-/ready", timeout=10.0)
            resp.raise_for_status()
            return {"ok": True, "detail": "reachable"}

        if name == "loki":
            resp = httpx.get(f"{loki.LOKI_URL}/ready", timeout=10.0)
            resp.raise_for_status()
            return {"ok": True, "detail": "reachable"}
    except Exception as e:
        return {"ok": False, "detail": f"{type(e).__name__}: {e}"}

    return {"ok": False, "detail": "no test defined"}
