"""Shared retry wrapper for real external APIs (Jira, GitHub, Azure, AWS).
Not used by prometheus.py/loki.py/deploys.py -- those talk to local
docker-compose services with different failure characteristics and don't
need it."""
import time

import httpx

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def request_with_retry(method: str, url: str, *, retries: int = 1, backoff: float = 1.0, **kwargs) -> httpx.Response:
    """Like httpx.request, but retries once (by default) on 429/5xx before
    raising. Raises on the final attempt same as a plain httpx call would."""
    attempt = 0
    while True:
        resp = httpx.request(method, url, **kwargs)
        if resp.status_code not in RETRYABLE_STATUS or attempt >= retries:
            resp.raise_for_status()
            return resp
        attempt += 1
        time.sleep(backoff)
