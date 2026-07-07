"""GET {DEMO_APP_URL}/deploys/latest/diff.
Stretch (Week 8+): swap for the real GitHub compare API."""
import os

import httpx

DEMO_APP_URL = os.environ.get("DEMO_APP_URL", "http://localhost:8001")

def latest_diff() -> str:
    try:
        resp = httpx.get(f"{DEMO_APP_URL}/deploys/latest/diff", timeout=10.0)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"ERROR fetching deploy diff: {e}"
    return resp.text[:2000]
