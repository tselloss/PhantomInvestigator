"""Agent API: /investigate runs the agent loop, / serves the operator UI."""
import json
import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

DEMO_APP_URL = os.environ.get("DEMO_APP_URL", "http://localhost:8001")

app = FastAPI(title="phantom-investigator")

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

# ---- UI + thin proxies to demo-app, so the browser only ever talks to the agent ----

_UI_PATH = os.path.join(os.path.dirname(__file__), "static", "index.html")

@app.get("/", response_class=HTMLResponse)
async def ui():
    return open(_UI_PATH).read()

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
