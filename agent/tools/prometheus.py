"""Query Prometheus over HTTP. Truncated so a bad query can't blow the context window."""
import os

import httpx

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

def query(promql: str) -> str:
    try:
        resp = httpx.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": promql}, timeout=10.0)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"ERROR querying Prometheus: {e}"
    return resp.text[:2000]
