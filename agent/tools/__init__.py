"""The agent's tool belt.

Tool descriptions are 50% of your prompt engineering — write them like
you're onboarding a junior SRE.
"""
from . import prometheus, loki, deploys, runbooks, jira, github_actions, azure_monitor, aws_cloudwatch, azure_devops, zendesk, diagnostics, version_registry
from schemas import Postmortem

DEPLOYMENT_ID_PROPERTY = {
    "type": ["integer", "null"],
    "description": (
        "This investigation's deployment id, if the alert mentions one (e.g. "
        "'Deployment: Acme Corp / prod (id 42)'). Passing it lets this call use "
        "that deployment's client-specific credential override, if one is "
        "configured, instead of the shared default -- always include it when "
        "the alert names a deployment."
    ),
}

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
            "properties": {
                "promql": {"type": "string"},
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
            },
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
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
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
            "properties": {
                "key": {"type": "string", "description": "Jira issue key, e.g. 'OPS-123'"},
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
            },
            "required": ["key"],
        },
    },
    {
        "name": "get_azure_devops_work_item",
        "description": (
            "Fetch an Azure Boards work item (User Story/Task/Bug) by its numeric id: title, "
            "type, state, description, and recent comments. Use this when the alert references "
            "a specific work item id -- it usually has the original symptom report and any "
            "follow-up context, the same role a Jira ticket plays for Jira-triggered incidents."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "work_item_id": {"type": "integer", "description": "Azure DevOps work item id, e.g. 4821"},
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
            },
            "required": ["work_item_id"],
        },
    },
    {
        "name": "get_azure_devops_commits",
        "description": (
            "List recent commits across all repos in the configured Azure DevOps project -- "
            "\"what shipped\" recently. Azure Repos equivalent of get_deploy_diff for teams whose "
            "code doesn't live on GitHub."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "default": 7, "description": "How many days back to look"},
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
            },
        },
    },
    {
        "name": "get_azure_devops_builds",
        "description": (
            "List recent Azure Pipelines builds for the configured project, optionally filtered to "
            "failed builds only. Check this early for CI/CD-triggered incidents -- the money query "
            "during an incident is usually whether the last build failed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hours": {"type": "integer", "default": 24, "description": "How many hours back to look"},
                "failed_only": {"type": "boolean", "default": False},
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
            },
        },
    },
    {
        "name": "search_azure_devops_work_items",
        "description": (
            "Search Azure Boards work items changed in the last N days whose title matches a query -- "
            "the Azure Boards equivalent of a Jira JQL search. Use when the alert doesn't name a "
            "specific work item id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text search terms, e.g. 'checkout error'"},
                "days": {"type": "integer", "default": 7},
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_github_runs",
        "description": "List the most recent GitHub Actions workflow runs for a repo, with status/conclusion/branch/sha. Check this for CI-triggered incidents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "'owner/name', e.g. 'tselloss/PhantomInvestigator'"},
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
            },
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
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
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
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
            },
            "required": ["repo", "base", "head"],
        },
    },
    {
        "name": "get_file_contents",
        "description": (
            "Fetch the COMPLETE current content of one file from a GitHub repo at a ref. "
            "Call this and read the result in full before including that file in "
            "submit_postmortem's proposed_fix_files -- never propose an edit to a file you "
            "haven't read this way. Errors (including 'file too large') mean that file is "
            "off-limits for proposed_fix_files this run."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "'owner/name'"},
                "path": {"type": "string", "description": "Repo-relative file path"},
                "ref": {"type": "string", "description": "Branch, tag, or commit sha to read at"},
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
            },
            "required": ["repo", "path", "ref"],
        },
    },
    {
        "name": "query_azure_logs",
        "description": "Run a KQL query against the configured Azure Log Analytics workspace. Use for incidents on Azure-hosted infra.",
        "input_schema": {
            "type": "object",
            "properties": {
                "kql": {"type": "string"},
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
            },
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
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
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
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
            },
            "required": ["log_group", "filter_pattern"],
        },
    },
    {
        "name": "search_support_tickets",
        "description": (
            "Search customer support tickets (Zendesk) for reports matching a query. "
            "Shows real customer-facing impact and timing -- a signal engineering tools "
            "alone don't have. Use alongside Jira/GitHub/metrics, not instead of them: "
            "correlate ticket volume/timing with a deploy or metric spike rather than "
            "treating ticket text as root-cause evidence on its own."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text search terms, e.g. 'checkout error'"},
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
            },
            "required": ["query"],
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
                "deployment_id": DEPLOYMENT_ID_PROPERTY,
            },
            "required": ["namespace", "metric_name"],
        },
    },
    {
        "name": "search_diagnostic_bundle",
        "description": (
            "Search uploaded diagnostic bundles (logs/metrics/config excerpts a support "
            "engineer submitted on the client's behalf) for a regex or substring. Use this "
            "for incidents on client infrastructure with no direct query access -- when "
            "query_metrics/search_logs/query_azure_*/query_aws_* aren't reachable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "deployment_id": {"type": "integer"},
                "query": {"type": "string"},
            },
            "required": ["deployment_id", "query"],
        },
    },
    {
        "name": "get_diagnostic_bundle_summary",
        "description": "List what diagnostic bundles (if any) have been uploaded for a deployment, and what each contains.",
        "input_schema": {
            "type": "object",
            "properties": {"deployment_id": {"type": "integer"}},
            "required": ["deployment_id"],
        },
    },
    {
        "name": "get_deployment_profile",
        "description": (
            "Look up everything on record for a deployment: its latest known version/build and how it was "
            "learned (self-report, uploaded bundle, or reconstructed from a past investigation). Call this "
            "FIRST whenever the alert mentions a deployment id -- don't assume nothing is known."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"deployment_id": {"type": "integer"}},
            "required": ["deployment_id"],
        },
    },
    {
        "name": "diff_against_known_release",
        "description": (
            "Compare a deployment's latest known version/build against the vendor's own release catalog and "
            "report what deviates from stock (different build, local patches, changed config fields). Use "
            "after get_deployment_profile shows a known version, to check whether this instance has drifted."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"deployment_id": {"type": "integer"}},
            "required": ["deployment_id"],
        },
    },
    {
        "name": "record_version_fingerprint",
        "description": (
            "Record a best-effort reconstruction of a deployment's version/build/drift when nothing was "
            "previously known (black-box case). Call this as soon as you establish ANY fact, even a "
            "low-confidence guess -- do not wait until submit_postmortem, since an investigation can end "
            "on the step/cost budget before reaching it. This is what turns 'nobody knows' into a permanent "
            "record the NEXT investigation for this deployment will see via get_deployment_profile."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "deployment_id": {"type": "integer"},
                "probable_version": {"type": ["string", "null"], "description": "Best guess, e.g. '1.4.x' if exact patch version is unclear"},
                "probable_build_sha": {"type": ["string", "null"]},
                "drift_notes": {"type": "string", "description": "JSON-encoded list of strings describing suspected deviations from stock"},
                "confidence": {"type": "number", "description": "0-1, calibrated to how solid the reconstruction evidence actually is"},
                "source_investigation_id": {"type": ["integer", "null"], "description": "This investigation's id, if mentioned in the alert text"},
            },
            "required": ["deployment_id", "drift_notes", "confidence"],
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

def execute_tool(name: str, args: dict, owner_user_id: int) -> str:
    """Dispatch. ALWAYS return a string, even on failure (models recover from
    error text; they cannot recover from your process crashing). owner_user_id
    is the CURRENT investigation's owner -- passed by loop.py directly, never
    read from `args` (which is model-controlled), so it can't be spoofed by a
    prompt-injected or hallucinated tool call. It's what keeps a deployment_id
    belonging to a different user from ever resolving to that user's stored
    credentials/data (see integration_credentials.resolve_credentials)."""
    try:
        match name:
            case "query_metrics":     return prometheus.query(args["promql"], owner_user_id, deployment_id=args.get("deployment_id"))
            case "search_logs":       return loki.search(args["logql"], owner_user_id, args.get("minutes", 5), deployment_id=args.get("deployment_id"))
            case "get_recent_changes":return deploys.latest_diff()
            case "search_runbooks":   return runbooks.search(args["query"], owner_user_id)
            case "get_jira_ticket":   return jira.get_ticket(args["key"], owner_user_id, deployment_id=args.get("deployment_id"))
            case "get_azure_devops_work_item": return azure_devops.get_work_item(args["work_item_id"], owner_user_id, deployment_id=args.get("deployment_id"))
            case "get_azure_devops_commits": return azure_devops.get_recent_commits(owner_user_id, deployment_id=args.get("deployment_id"), days=args.get("days", 7))
            case "get_azure_devops_builds": return azure_devops.get_recent_builds(owner_user_id, deployment_id=args.get("deployment_id"), hours=args.get("hours", 24), failed_only=args.get("failed_only", False))
            case "search_azure_devops_work_items": return azure_devops.search_work_items(args["query"], owner_user_id, deployment_id=args.get("deployment_id"), days=args.get("days", 7))
            case "get_github_runs":   return github_actions.get_recent_runs(args["repo"], owner_user_id, deployment_id=args.get("deployment_id"))
            case "get_github_run_logs": return github_actions.get_run_logs(args["repo"], args["run_id"], owner_user_id, deployment_id=args.get("deployment_id"))
            case "get_deploy_diff":   return github_actions.get_deploy_diff(args["repo"], args["base"], args["head"], owner_user_id, deployment_id=args.get("deployment_id"))
            case "get_file_contents": return github_actions.get_file_contents(args["repo"], args["path"], args["ref"], owner_user_id, deployment_id=args.get("deployment_id"))
            case "query_azure_logs":  return azure_monitor.query_logs(args["kql"], owner_user_id, deployment_id=args.get("deployment_id"))
            case "query_azure_metrics": return azure_monitor.query_metrics(args["resource_id"], args["metric_namespace"], args["metric_names"], owner_user_id, deployment_id=args.get("deployment_id"))
            case "search_support_tickets": return zendesk.search_tickets(args["query"], owner_user_id, deployment_id=args.get("deployment_id"))
            case "query_aws_logs":    return aws_cloudwatch.query_logs(args["log_group"], args["filter_pattern"], owner_user_id, args.get("minutes", 15), deployment_id=args.get("deployment_id"))
            case "query_aws_metrics": return aws_cloudwatch.query_metrics(args["namespace"], args["metric_name"], owner_user_id, args.get("dimensions_json", "[]"), deployment_id=args.get("deployment_id"))
            case "search_diagnostic_bundle": return diagnostics.search_diagnostic_bundle(args["deployment_id"], args["query"], owner_user_id)
            case "get_diagnostic_bundle_summary": return diagnostics.get_diagnostic_bundle_summary(args["deployment_id"], owner_user_id)
            case "get_deployment_profile": return version_registry.get_deployment_profile(args["deployment_id"], owner_user_id)
            case "diff_against_known_release": return version_registry.diff_against_known_release(args["deployment_id"], owner_user_id)
            case "record_version_fingerprint":
                return version_registry.record_version_fingerprint(
                    args["deployment_id"], args.get("probable_version"), args.get("probable_build_sha"),
                    args["drift_notes"], args["confidence"], owner_user_id, args.get("source_investigation_id"),
                )
            case _:                   return f"ERROR: unknown tool {name}"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
