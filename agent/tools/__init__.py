"""The agent's tool belt.

Tool descriptions are 50% of your prompt engineering — write them like
you're onboarding a junior SRE.
"""
from . import prometheus, loki, deploys, runbooks, jira, github_actions, azure_monitor, aws_cloudwatch
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
        "name": "get_jira_ticket",
        "description": (
            "Fetch a Jira ticket's summary, description, status, and recent comments. "
            "Use this first when investigating a Jira-triggered incident — the ticket "
            "usually has the original symptom report and any follow-up context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string", "description": "Jira issue key, e.g. 'OPS-123'"}},
            "required": ["key"],
        },
    },
    {
        "name": "get_github_runs",
        "description": "List the most recent GitHub Actions workflow runs for a repo, with status/conclusion/branch/sha. Check this for CI-triggered incidents.",
        "input_schema": {
            "type": "object",
            "properties": {"repo": {"type": "string", "description": "'owner/name', e.g. 'tselloss/PhantomInvestigator'"}},
            "required": ["repo"],
        },
    },
    {
        "name": "get_github_run_logs",
        "description": "Fetch logs for the failed jobs in a specific GitHub Actions run. Use after get_github_runs identifies a failing run_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "run_id": {"type": "integer"},
            },
            "required": ["repo", "run_id"],
        },
    },
    {
        "name": "get_deploy_diff",
        "description": (
            "Get the real code diff between two commits/branches via GitHub's compare API "
            "(base...head). Use this to check what actually changed in a suspect deploy — "
            "get the base/head shas from get_github_runs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "base": {"type": "string"},
                "head": {"type": "string"},
            },
            "required": ["repo", "base", "head"],
        },
    },
    {
        "name": "query_azure_logs",
        "description": "Run a KQL query against the configured Azure Log Analytics workspace. Use for incidents on Azure-hosted infra.",
        "input_schema": {
            "type": "object",
            "properties": {"kql": {"type": "string"}},
            "required": ["kql"],
        },
    },
    {
        "name": "query_azure_metrics",
        "description": "Fetch Azure Monitor metrics for a resource, e.g. 'Percentage CPU', 'Network In'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_id": {"type": "string", "description": "Full Azure resource ID"},
                "metric_namespace": {"type": "string", "description": "e.g. 'Microsoft.Compute/virtualMachines'"},
                "metric_names": {"type": "string", "description": "Comma-separated metric names"},
            },
            "required": ["resource_id", "metric_namespace", "metric_names"],
        },
    },
    {
        "name": "query_aws_logs",
        "description": "Search a CloudWatch log group with a filter pattern over the last N minutes. Use for incidents on AWS-hosted infra.",
        "input_schema": {
            "type": "object",
            "properties": {
                "log_group": {"type": "string"},
                "filter_pattern": {"type": "string"},
                "minutes": {"type": "integer", "default": 15},
            },
            "required": ["log_group", "filter_pattern"],
        },
    },
    {
        "name": "query_aws_metrics",
        "description": "Fetch CloudWatch metric statistics (avg/max over the last hour) for a namespace + metric name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "e.g. 'AWS/EC2', 'AWS/RDS'"},
                "metric_name": {"type": "string", "description": "e.g. 'CPUUtilization'"},
                "dimensions_json": {"type": "string", "description": "JSON array, e.g. '[{\"Name\": \"InstanceId\", \"Value\": \"i-123\"}]'"},
            },
            "required": ["namespace", "metric_name"],
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
            case "get_jira_ticket":   return jira.get_ticket(args["key"])
            case "get_github_runs":   return github_actions.get_recent_runs(args["repo"])
            case "get_github_run_logs": return github_actions.get_run_logs(args["repo"], args["run_id"])
            case "get_deploy_diff":   return github_actions.get_deploy_diff(args["repo"], args["base"], args["head"])
            case "query_azure_logs":  return azure_monitor.query_logs(args["kql"])
            case "query_azure_metrics": return azure_monitor.query_metrics(args["resource_id"], args["metric_namespace"], args["metric_names"])
            case "query_aws_logs":    return aws_cloudwatch.query_logs(args["log_group"], args["filter_pattern"], args.get("minutes", 15))
            case "query_aws_metrics": return aws_cloudwatch.query_metrics(args["namespace"], args["metric_name"], args.get("dimensions_json", "[]"))
            case _:                   return f"ERROR: unknown tool {name}"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
