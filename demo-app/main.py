"""Demo e-shop service the agent will investigate.

Run locally: uvicorn main:app --reload
"""
import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

import faults

log = structlog.get_logger()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/demo")

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    price NUMERIC NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = AsyncConnectionPool(DATABASE_URL, open=False)
    await pool.open()
    async with pool.connection() as conn:
        await conn.execute(CREATE_TABLES_SQL)
        row = await (await conn.execute("SELECT count(*) FROM products")).fetchone()
        if row[0] == 0:
            await conn.execute("INSERT INTO products (name, price) VALUES (%s, %s)", ("keyboard", 49.0))
    app.state.db = pool
    yield
    await pool.close()

app = FastAPI(title="demo-shop", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)  # -> /metrics for Prometheus

@app.middleware("http")
async def fault_middleware(request, call_next):
    await faults.apply_request_effects(request.url.path)
    return await call_next(request)

@app.get("/health")
async def health():
    return {
        "ok": True,
        "active_faults": faults.active_faults(),
        # memory_leak has no effect on status code/latency (see faults.py) --
        # its only visible signal is this growing forever, even across
        # "Clear faults", same as a real unbounded cache would.
        "leaked_cache_mb": len(faults._leaky_cache),
    }

@app.get("/products")
async def products():
    async with app.state.db.connection() as conn:
        rows = await (await conn.execute("SELECT id, name, price FROM products")).fetchall()
    return [{"id": r[0], "name": r[1], "price": float(r[2])} for r in rows]

@app.post("/checkout")
async def checkout():
    await faults.apply_checkout_effects()
    log.info("checkout.started")
    async with app.state.db.connection() as conn:
        row = await (await conn.execute(
            "INSERT INTO orders (status) VALUES (%s) RETURNING id", ("confirmed",)
        )).fetchone()
    return {"order_id": row[0], "status": "confirmed"}

# ---- fault control plane (the "chaos" API) ----

@app.post("/faults/{name}")
async def inject(name: str):
    if name not in faults.FAULTS:
        raise HTTPException(404, f"unknown fault, options: {list(faults.FAULTS)}")
    import time
    f = faults.FAULTS[name]
    f.active, f.injected_at = True, time.time()
    log.warning("deploy.completed", version=f"v1.{int(f.injected_at)}")  # looks like a deploy!
    return {"injected": name}

@app.delete("/faults")
async def clear():
    for f in faults.FAULTS.values():
        f.active = False
    return {"cleared": True}

@app.get("/deploys/latest/diff")
async def latest_diff():
    """The agent's get_recent_changes tool calls this."""
    active = [f for f in faults.FAULTS.values() if f.active]
    if not active:
        return {"diff": "no changes in the last 24h"}
    if len(active) == 1:
        return {"diff": active[-1].fake_diff, "deployed_at": active[-1].injected_at}
    # Multiple faults active at once — surface every recent change, not just
    # the last one, or an incident with two root causes would look like one.
    combined = "\n\n".join(f"--- deploy at {f.injected_at} ---\n{f.fake_diff}" for f in active)
    return {
        "diff": combined,
        "deployed_at": max(f.injected_at for f in active),
        "note": f"{len(active)} separate recent changes found",
    }

class DebugLogRequest(BaseModel):
    message: str

@app.post("/debug/inject-log")
async def debug_inject_log(req: DebugLogRequest):
    """Test-only: write an arbitrary log line, so evals can plant an
    adversarial (prompt-injection) message for search_logs to surface."""
    log.error("debug.injected", message=req.message)
    return {"injected": True}
