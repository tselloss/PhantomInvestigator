"""Query Prometheus over HTTP. Truncated so a bad query can't blow the context window."""
import os

import httpx

import integration_credentials

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")


def _config(user_id: int, deployment_id: int | None = None, client_id: int | None = None) -> dict:
    override = integration_credentials.resolve_credentials(
        "prometheus", user_id, deployment_id=deployment_id, client_id=client_id
    ) or {}
    return {"url": override.get("url") or PROMETHEUS_URL}


def query(promql: str, user_id: int, deployment_id: int | None = None) -> str:
    url = _config(user_id, deployment_id=deployment_id)["url"]
    try:
        resp = httpx.get(f"{url}/api/v1/query", params={"query": promql}, timeout=10.0)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"ERROR querying Prometheus: {e}"
    return resp.text[:2000]
