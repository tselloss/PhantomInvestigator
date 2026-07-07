"""Fault injection engine — the heart of the demo.

Each fault degrades the app in a way that is VISIBLE in metrics/logs,
and each has a fake "deploy diff" attached, so injecting a fault looks
like a bad deploy just went out. That diff is what the agent will find
via the get_recent_changes tool.
"""
import time, random, asyncio
from dataclasses import dataclass, field

import structlog
from fastapi import HTTPException

log = structlog.get_logger()

@dataclass
class Fault:
    name: str
    description: str          # ground truth — used by the eval harness, NEVER shown to the agent
    fake_diff: str            # what "changed in the last deploy"
    active: bool = False
    injected_at: float | None = None

FAULTS: dict[str, Fault] = {
    "slow_db": Fault(
        name="slow_db",
        description="DB connection pool exhausted -> queries queue -> latency spike on /checkout",
        fake_diff=(
            "--- a/db.py\n+++ b/db.py\n"
            "-POOL_SIZE = 20\n+POOL_SIZE = 2\n"
        ),
    ),
    "bad_deploy": Fault(
        name="bad_deploy",
        description="New code path raises KeyError on /checkout for ~30% of requests -> 500 spike",
        fake_diff=(
            "--- a/checkout.py\n+++ b/checkout.py\n"
            "+    discount = payload[\"discount_code\"]  # oops: key not always present\n"
        ),
    ),
    "memory_leak": Fault(
        name="memory_leak",
        description="Per-request cache never evicts -> RSS climbs -> eventual OOM behaviour",
        fake_diff=(
            "--- a/cache.py\n+++ b/cache.py\n"
            "+_cache: dict = {}  # TODO add eviction (narrator: they did not add eviction)\n"
        ),
    ),
    "error_spike": Fault(
        name="error_spike",
        description="Deploy misconfigured payment provider timeout (30s -> 0.05s) -> checkout returns 502s",
        fake_diff=(
            "--- a/payments.py\n+++ b/payments.py\n"
            "-TIMEOUT = 30\n+TIMEOUT = 0.05  # 'performance optimization'\n"
        ),
    ),
}

_leaky_cache: list[bytes] = []  # for memory_leak

def active_faults() -> list[str]:
    return [f.name for f in FAULTS.values() if f.active]

async def apply_request_effects(path: str) -> None:
    """Called by middleware on every request, BEFORE routing resolves.

    Only non-error-producing effects belong here: raising/short-circuiting
    this early means Prometheus's instrumentation (which only sees requests
    that reach a resolved route) never observes the failure. Error-producing
    faults live in apply_checkout_effects() instead, called from inside the
    /checkout endpoint after routing has happened.
    """
    if FAULTS["slow_db"].active and path == "/checkout":
        delay = random.uniform(1.5, 4.0)
        await asyncio.sleep(delay)
        log.warning("db.slow_query", query="SELECT * FROM orders", duration_s=round(delay, 2))

    if FAULTS["memory_leak"].active:
        _leaky_cache.append(b"x" * 1_000_000)
        log.warning("cache.grew", size_mb=len(_leaky_cache))

async def apply_checkout_effects() -> None:
    """Called from inside the /checkout endpoint. Raises HTTPException for
    faults that should produce an error response — HTTPException is caught
    right at the routing boundary and turned into a normal Response, so it
    still flows back through Prometheus's instrumentation correctly."""
    if FAULTS["bad_deploy"].active and random.random() < 0.3:
        log.error("checkout.failed", error="KeyError: 'discount_code'")
        raise HTTPException(500, "KeyError: 'discount_code'")

    if FAULTS["error_spike"].active:
        log.error("payments.timeout", provider="stripe", timeout_s=0.05)
        raise HTTPException(502, "payment provider timeout")
