"""Agent API. JSON endpoints live under /api (auth-gated by AuthMiddleware
below); everything else (the React app, /health, /webhooks/*, /auth/*) is
public -- the SPA shell has to load before it can even show a login form."""
import json
import os
import time

import httpx
import structlog
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

import billing
import clients
import diagnostics
import fix_proposals
import investigations
import screenshots
import vision
from rate_limit import RateLimitMiddleware
from routes.auth import SESSION_COOKIE, get_current_user, user_tos_accepted, verify_session_cookie
from routes.auth import router as auth_router
from routes.checkin import router as checkin_router
from routes.client_integrations import router as client_integrations_router
from routes.client_tickets import router as client_tickets_router
from routes.clients import router as clients_router
from routes.diagnostics import router as diagnostics_router
from routes.evals import router as evals_router
from routes.investigations import router as investigations_router
from routes.runbooks import router as runbooks_router
from routes.settings import router as settings_router
from routes.webhooks import router as webhooks_router

log = structlog.get_logger(__name__)

DEMO_APP_URL = os.environ.get("DEMO_APP_URL", "http://localhost:8001")

try:
    APP_VERSION = open("VERSION").read().strip()
except FileNotFoundError:
    APP_VERSION = "dev"


class AuthMiddleware(BaseHTTPMiddleware):
    """Gates everything under /api -- the JSON data the React app fetches
    after it has already decided (via GET /auth/me) whether to show the
    login page. /webhooks/* and /auth/* are intentionally not under /api:
    webhooks authenticate via their own secret/signature, and /auth/* has
    to be reachable while logged out."""

    async def dispatch(self, request, call_next):
        if request.url.path.startswith("/api/"):
            user = verify_session_cookie(request.cookies.get(SESSION_COOKIE))
            if not user:
                return JSONResponse({"detail": "not authenticated"}, status_code=401)
            if not user_tos_accepted(user["user_id"]):
                return JSONResponse({"detail": "terms of service not accepted"}, status_code=403)
            request.state.user = user
        return await call_next(request)


app = FastAPI(title="phantom-investigator", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def log_requests(request, call_next):
    """Replaces uvicorn's default access log (disabled via --no-access-log
    in the Dockerfile CMD), which would otherwise print the full request
    line -- including query strings like the Jira webhook's ?secret=... --
    to container logs. Deliberately logs request.url.path only, never the
    query string or full URL."""
    start = time.monotonic()
    response = await call_next(request)
    log.info(
        "http.request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round((time.monotonic() - start) * 1000, 1),
    )
    return response


app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

app.include_router(webhooks_router)
app.include_router(checkin_router)
app.include_router(auth_router)
app.include_router(clients_router, prefix="/api")
app.include_router(client_integrations_router, prefix="/api")
app.include_router(client_tickets_router, prefix="/api")
app.include_router(diagnostics_router, prefix="/api")
app.include_router(investigations_router, prefix="/api")
app.include_router(runbooks_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(evals_router, prefix="/api")


class InvestigateRequest(BaseModel):
    alert: str
    deployment_id: int | None = None
    screenshot_id: int | None = None


MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024
ALLOWED_SCREENSHOT_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


@app.post("/api/investigate/screenshot")
async def investigate_screenshot(
    file: UploadFile = File(...), deployment_id: int | None = Form(None), user: dict = Depends(get_current_user)
):
    """Uploaded separately, before an investigation starts: the UI's actual
    submit path (GET /api/investigate/stream, below) is an EventSource and
    can't carry a multipart body. The caller uploads here first, gets back a
    vision_description to fold into the alert text client-side, then starts
    the investigation as normal (optionally passing the returned id back so
    it gets linked to the investigation once one exists)."""
    if file.content_type not in ALLOWED_SCREENSHOT_TYPES:
        raise HTTPException(415, f"unsupported content type: {file.content_type}")

    image_bytes = await file.read()
    if len(image_bytes) > MAX_SCREENSHOT_BYTES:
        raise HTTPException(413, f"screenshot exceeds {MAX_SCREENSHOT_BYTES} byte limit")

    user_id = user["user_id"]
    vision_description = None
    vision_status = "failed"
    try:
        vision_description = vision.describe_screenshot(image_bytes, file.content_type, user_id)
        vision_status = "ok"
    except Exception:
        pass  # keep the screenshot on record even if the vision call failed; UI falls back to guided text fields

    screenshot = screenshots.store_screenshot(
        file.filename or "screenshot",
        file.content_type,
        image_bytes,
        user_id,
        deployment_id=deployment_id,
        vision_description=vision_description,
        vision_status=vision_status,
    )

    if deployment_id is not None and vision_description:
        diagnostics.store_bundle(
            deployment_id, user_id, file.filename or "screenshot", screenshot_excerpt=vision_description
        )

    return {
        "id": screenshot["id"],
        "filename": screenshot["filename"],
        "vision_description": vision_description,
        "vision_status": vision_status,
    }


@app.post("/api/investigate")
async def investigate(req: InvestigateRequest, user: dict = Depends(get_current_user)):
    from loop import run_agent

    user_id = user["user_id"]
    alert_text = clients.deployment_note(req.deployment_id, user_id) + req.alert

    duplicate = investigations.find_recent_duplicate("manual", None, req.deployment_id, alert_text, user_id)
    if duplicate is not None:
        return {**(duplicate["result"] or {}), "investigation_id": duplicate["id"], "deduped": True}

    budget = billing.check_budget(user_id)
    if not budget["allowed"]:
        raise HTTPException(
            402,
            f"Monthly AI spend cap of ${budget['limit_usd']:.2f} reached "
            f"(${budget['spent_usd']:.2f} spent this month). Raise it in Settings → Profile.",
        )

    investigation_id = investigations.start("manual", None, alert_text, user_id, deployment_id=req.deployment_id)
    if req.screenshot_id is not None:
        screenshots.link_to_investigation(req.screenshot_id, investigation_id)
    loop_alert_text = clients.build_loop_alert_text(alert_text, investigation_id, req.deployment_id, user_id)
    try:
        result = run_agent(loop_alert_text, user_id, deployment_id=req.deployment_id)
    except Exception as e:
        investigations.finish(investigation_id, "error", {"error": f"{type(e).__name__}: {e}"})
        raise
    pending_fix_action = None
    if result.get("postmortem"):
        deployment = clients.get_deployment(req.deployment_id, user_id) if req.deployment_id else None
        pending_fix_action = fix_proposals.build_pending_fix_action(
            result["postmortem"], deployment, result.get("files_read", []), user_id
        )
    investigations.finish(
        investigation_id, "done" if result.get("postmortem") else "partial", result,
        pending_fix_action=pending_fix_action,
    )
    return {**result, "investigation_id": investigation_id, "deduped": False}


@app.get("/api/investigate/stream")
async def investigate_stream(
    alert: str = "Manual investigation triggered from UI.",
    deployment_id: int | None = None,
    screenshot_id: int | None = None,
    user: dict = Depends(get_current_user),
):
    """Same investigation as POST /api/investigate, but streamed as
    Server-Sent Events so a UI can show tool calls as they happen instead of
    blocking for 20-40s. GET + query param (not POST + body) because
    EventSource, the browser API for consuming SSE, only supports GET."""
    user_id = user["user_id"]

    def event_gen():
        from loop import run_agent_stream

        alert_text = clients.deployment_note(deployment_id, user_id) + alert

        duplicate = investigations.find_recent_duplicate("manual", None, deployment_id, alert_text, user_id)
        if duplicate is not None:
            data = {**(duplicate["result"] or {}), "investigation_id": duplicate["id"], "deduped": True}
            yield f"data: {json.dumps({'type': 'final', 'data': data})}\n\n"
            return

        budget = billing.check_budget(user_id)
        if not budget["allowed"]:
            data = {
                "result": f"Stopped: monthly AI spend cap of ${budget['limit_usd']:.2f} reached "
                f"(${budget['spent_usd']:.2f} spent this month).",
                "partial": True,
                "budget_exceeded": True,
            }
            yield f"data: {json.dumps({'type': 'final', 'data': data})}\n\n"
            return

        investigation_id = investigations.start("manual", None, alert_text, user_id, deployment_id=deployment_id)
        if screenshot_id is not None:
            screenshots.link_to_investigation(screenshot_id, investigation_id)
        loop_alert_text = clients.build_loop_alert_text(alert_text, investigation_id, deployment_id, user_id)
        # trace records step_start/tool_call/tool_result (not "final" -- that's
        # already stored as result) so the detail page can replay this run's
        # timeline later, including a partial trace on an errored/cut-short run.
        trace = []
        result = None
        try:
            for event in run_agent_stream(loop_alert_text, user_id, deployment_id=deployment_id):
                if event["type"] == "final":
                    event["data"]["investigation_id"] = investigation_id
                    result = event["data"]
                else:
                    trace.append(event)
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            investigations.finish(investigation_id, "error", {"error": f"{type(e).__name__}: {e}"}, trace=trace)
            error_data = {"result": f"ERROR: {e}", "partial": True, "investigation_id": investigation_id}
            yield f"data: {json.dumps({'type': 'final', 'data': error_data})}\n\n"
            return
        pending_fix_action = None
        if (result or {}).get("postmortem"):
            deployment = clients.get_deployment(deployment_id, user_id) if deployment_id else None
            pending_fix_action = fix_proposals.build_pending_fix_action(
                result["postmortem"], deployment, result.get("files_read", []), user_id
            )
        investigations.finish(
            investigation_id, "done" if (result or {}).get("postmortem") else "partial", result or {},
            pending_fix_action=pending_fix_action, trace=trace,
        )

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"ok": True, "version": APP_VERSION}


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


@app.post("/api/demo/checkout-test")
async def demo_checkout_test(count: int = 5):
    """Fires a few real requests at demo-app's /checkout and reports
    status/latency per request -- so injecting a fault has something visible
    to point at (a slow/erroring request feed) instead of just trusting the
    button worked."""
    count = max(1, min(count, 20))
    results = []
    for _ in range(count):
        start = time.monotonic()
        try:
            resp = httpx.post(f"{DEMO_APP_URL}/checkout", timeout=10.0)
            results.append({"status_code": resp.status_code, "latency_ms": round((time.monotonic() - start) * 1000)})
        except httpx.HTTPError as e:
            results.append({"status_code": None, "latency_ms": round((time.monotonic() - start) * 1000), "error": str(e)})
    return {"results": results}


# ---- React app (built into static/ui by the Docker image) ----

_UI_DIST = os.path.join(os.path.dirname(__file__), "static", "ui")
_UI_INDEX = os.path.join(_UI_DIST, "index.html")

if os.path.isdir(os.path.join(_UI_DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(_UI_DIST, "assets")), name="ui-assets")

# Public (no auth) so the /terms page's link to the full document works for
# logged-out visitors too -- same tier as /health, not gated by AuthMiddleware
# since that only intercepts /api/*. Copied into the image by the Dockerfile.
_LEGAL_DIR = os.path.join(os.path.dirname(__file__), "docs", "legal")
if os.path.isdir(_LEGAL_DIR):
    app.mount("/legal", StaticFiles(directory=_LEGAL_DIR), name="legal-docs")


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
