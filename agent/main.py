"""Agent API. JSON endpoints live under /api (auth-gated by AuthMiddleware
below); everything else (the React app, /health, /webhooks/*, /auth/*) is
public -- the SPA shell has to load before it can even show a login form."""
import json
import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

import investigations
from routes.auth import SESSION_COOKIE, verify_session_cookie
from routes.auth import router as auth_router
from routes.evals import router as evals_router
from routes.investigations import router as investigations_router
from routes.runbooks import router as runbooks_router
from routes.settings import router as settings_router
from routes.webhooks import router as webhooks_router

DEMO_APP_URL = os.environ.get("DEMO_APP_URL", "http://localhost:8001")


class AuthMiddleware(BaseHTTPMiddleware):
    """Gates everything under /api -- the JSON data the React app fetches
    after it has already decided (via GET /auth/me) whether to show the
    login page. /webhooks/* and /auth/* are intentionally not under /api:
    webhooks authenticate via their own secret/signature, and /auth/* has
    to be reachable while logged out."""

    async def dispatch(self, request, call_next):
        if request.url.path.startswith("/api/"):
            username = verify_session_cookie(request.cookies.get(SESSION_COOKIE))
            if not username:
                return JSONResponse({"detail": "not authenticated"}, status_code=401)
        return await call_next(request)


app = FastAPI(title="phantom-investigator")
app.add_middleware(AuthMiddleware)

app.include_router(webhooks_router)
app.include_router(auth_router)
app.include_router(investigations_router, prefix="/api")
app.include_router(runbooks_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(evals_router, prefix="/api")


class InvestigateRequest(BaseModel):
    alert: str


@app.post("/api/investigate")
async def investigate(req: InvestigateRequest):
    from loop import run_agent

    investigation_id = investigations.start("manual", None, req.alert)
    try:
        result = run_agent(req.alert)
    except Exception as e:
        investigations.finish(investigation_id, "error", {"error": f"{type(e).__name__}: {e}"})
        raise
    investigations.finish(investigation_id, "done" if result.get("postmortem") else "partial", result)
    return result


@app.get("/api/investigate/stream")
async def investigate_stream(alert: str = "Manual investigation triggered from UI."):
    """Same investigation as POST /api/investigate, but streamed as
    Server-Sent Events so a UI can show tool calls as they happen instead of
    blocking for 20-40s. GET + query param (not POST + body) because
    EventSource, the browser API for consuming SSE, only supports GET."""

    def event_gen():
        from loop import run_agent_stream

        investigation_id = investigations.start("manual", None, alert)
        result = None
        try:
            for event in run_agent_stream(alert):
                if event["type"] == "final":
                    result = event["data"]
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            investigations.finish(investigation_id, "error", {"error": f"{type(e).__name__}: {e}"})
            yield f"data: {json.dumps({'type': 'final', 'data': {'result': f'ERROR: {e}', 'partial': True}})}\n\n"
            return
        investigations.finish(investigation_id, "done" if (result or {}).get("postmortem") else "partial", result or {})

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/api/demo/health")
async def demo_health():
    try:
        resp = httpx.get(f"{DEMO_APP_URL}/health", timeout=10.0)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"demo-app unreachable: {e}")
    return resp.json()


@app.post("/api/demo/faults/{name}")
async def demo_inject(name: str):
    resp = httpx.post(f"{DEMO_APP_URL}/faults/{name}", timeout=10.0)
    return resp.json()


@app.delete("/api/demo/faults")
async def demo_clear():
    resp = httpx.delete(f"{DEMO_APP_URL}/faults", timeout=10.0)
    return resp.json()


# ---- React app (built into static/ui by the Docker image) ----

_UI_DIST = os.path.join(os.path.dirname(__file__), "static", "ui")
_UI_INDEX = os.path.join(_UI_DIST, "index.html")

if os.path.isdir(os.path.join(_UI_DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(_UI_DIST, "assets")), name="ui-assets")


def _render_ui() -> str:
    if os.path.exists(_UI_INDEX):
        return open(_UI_INDEX, encoding="utf-8").read()
    return (
        "<h1>Phantom Investigator</h1>"
        "<p>React UI not built into this image. Run <code>npm run dev</code> in "
        "<code>ui/</code> for local development, or <code>docker compose up --build</code> "
        "to serve the built assets from here.</p>"
    )


@app.get("/", response_class=HTMLResponse)
async def ui_root():
    return _render_ui()


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def ui_spa_fallback(full_path: str):
    """Client-side routes (e.g. /investigations/5, /login) are handled by
    React Router -- every one of them still needs the same index.html on a
    hard refresh. Registered last so it never shadows /api, /assets,
    /webhooks, /auth, or /health above."""
    return _render_ui()
