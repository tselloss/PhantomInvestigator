"""Agent API: /investigate runs the agent loop, / serves the operator UI."""
import json
import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from routes.webhooks import router as webhooks_router

DEMO_APP_URL = os.environ.get("DEMO_APP_URL", "http://localhost:8001")

app = FastAPI(title="phantom-investigator")
app.include_router(webhooks_router)

class InvestigateRequest(BaseModel):
    alert: str

@app.post("/investigate")
async def investigate(req: InvestigateRequest):
    from loop import run_agent
    return run_agent(req.alert)

@app.get("/investigate/stream")
async def investigate_stream(alert: str = "Manual investigation triggered from UI."):
    """Same investigation as POST /investigate, but streamed as Server-Sent
    Events so a UI can show tool calls as they happen instead of blocking
    for 20-40s. GET + query param (not POST + body) because EventSource,
    the browser API for consuming SSE, only supports GET."""
    def event_gen():
        from loop import run_agent_stream
        for event in run_agent_stream(alert):
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_gen(), media_type="text/event-stream")

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/investigations")
async def investigations_feed(limit: int = 20):
    from investigations import list_recent
    return list_recent(limit)

# ---- UI (React, built into static/ui by the Docker image) + thin proxies
# to demo-app, so the browser only ever talks to the agent ----

_UI_DIST = os.path.join(os.path.dirname(__file__), "static", "ui")

if os.path.isdir(os.path.join(_UI_DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(_UI_DIST, "assets")), name="ui-assets")

@app.get("/", response_class=HTMLResponse)
async def ui():
    index_path = os.path.join(_UI_DIST, "index.html")
    if os.path.exists(index_path):
        return open(index_path, encoding="utf-8").read()
    return (
        "<h1>Phantom Investigator</h1>"
        "<p>React UI not built into this image. Run <code>npm run dev</code> in "
        "<code>ui/</code> for local development, or <code>docker compose up --build</code> "
        "to serve the built assets from here.</p>"
    )

@app.get("/demo/health")
async def demo_health():
    try:
        resp = httpx.get(f"{DEMO_APP_URL}/health", timeout=10.0)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"demo-app unreachable: {e}")
    return resp.json()

@app.post("/demo/faults/{name}")
async def demo_inject(name: str):
    resp = httpx.post(f"{DEMO_APP_URL}/faults/{name}", timeout=10.0)
    return resp.json()

@app.delete("/demo/faults")
async def demo_clear():
    resp = httpx.delete(f"{DEMO_APP_URL}/faults", timeout=10.0)
    return resp.json()
