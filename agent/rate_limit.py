"""In-memory per-IP rate limiting for the handful of unauthenticated,
abuse-prone endpoints: login/register (brute force) and webhooks (flooding
to burn AI spend or just DoS the agent loop). Plain in-memory sliding window
-- no new dependency, fine for a single uvicorn worker. Would need a shared
store (e.g. the redis already running for Langfuse) if this ever moves to
multiple workers/replicas, since each process would otherwise count
independently.

Note for webhook limits specifically: Jira/GitHub deliveries can share
source IPs with other, unrelated webhooks on the same platform, so the
webhook limit is set generously (well above normal retry volume) rather
than tight -- this is a coarse abuse backstop, not a precise per-tenant
limit."""
import time
from collections import defaultdict, deque

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

log = structlog.get_logger(__name__)

_WINDOW_SECONDS = 60
_AUTH_LIMIT = 10
_WEBHOOK_LIMIT = 60

_hits: dict[str, deque] = defaultdict(deque)


def reset() -> None:
    """Test-only: clear all tracked hits between tests."""
    _hits.clear()


def _limit_for(path: str) -> int | None:
    if path in ("/auth/login", "/auth/register"):
        return _AUTH_LIMIT
    if path.startswith("/webhooks/"):
        return _WEBHOOK_LIMIT
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        limit = _limit_for(request.url.path)
        if limit is None:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{request.url.path}"
        now = time.monotonic()
        dq = _hits[key]
        while dq and now - dq[0] > _WINDOW_SECONDS:
            dq.popleft()

        if len(dq) >= limit:
            log.warning("rate_limit.exceeded", path=request.url.path, client=client_ip)
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)

        dq.append(now)
        return await call_next(request)
