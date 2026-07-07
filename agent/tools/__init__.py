"""The agent's tool belt.

Tool descriptions are 50% of your prompt engineering — write them like
you're onboarding a junior SRE. Weeks 3-5 implement these one by one.
"""
from . import prometheus, loki, deploys, runbooks
from schemas import Postmortem

TOOL_SCHEMAS = [
    {
        "name": "query_metrics",
        "description": (
            "Run a PromQL query against Prometheus. Useful queries:\n"
            "- error rate: rate(http_requests_total{status=~\"5..\"}[5m])\n"
            "- p95 latency: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))\n"
            "Returns the query result as JSON (truncated)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"promql": {"type": "string"}},
            "required": ["promql"],
        },
    },
    {
        "name": "search_logs",
        "description": (
            "Search app logs in Loki with LogQL over the last N minutes. "
            "Logs are labeled by container name, not service name. "
            "Example: {container=~\".*demo-app.*\"} |= \"error\". Returns up to 50 lines. "
            "Default window is intentionally short (5 min): this environment reuses the "
            "same log stream across incidents, so older log lines may belong to a "
            "previous, already-resolved incident. Only widen the window if the current "
            "alert genuinely predates 5 minutes ago, and always cross-check log "
            "timestamps against get_recent_changes' deployed_at before treating a log "
            "line as evidence for the current incident."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "logql": {"type": "string"},
                "minutes": {"type": "integer", "default": 5},
            },
            "required": ["logql"],
        },
    },
    {
        "name": "get_recent_changes",
        "description": "Get the diff of the most recent deploy to demo-shop. Most incidents follow deploys — check this early.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_runbooks",
        "description": "Semantic search over runbooks and past postmortems. Use symptom descriptions as the query, e.g. 'latency spike checkout database'.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "submit_postmortem",
        "description": (
            "Submit your final, structured incident postmortem. Call this exactly once, "
            "when you have a confident root-cause hypothesis backed by tool evidence. "
            "This ends the investigation."
        ),
        "input_schema": Postmortem.model_json_schema(),
    },
]

def execute_tool(name: str, args: dict) -> str:
    """Dispatch. ALWAYS return a string, even on failure (models recover from
    error text; they cannot recover from your process crashing)."""
    try:
        match name:
            case "query_metrics":     return prometheus.query(args["promql"])
            case "search_logs":       return loki.search(args["logql"], args.get("minutes", 15))
            case "get_recent_changes":return deploys.latest_diff()
            case "search_runbooks":   return runbooks.search(args["query"])
            case _:                   return f"ERROR: unknown tool {name}"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
