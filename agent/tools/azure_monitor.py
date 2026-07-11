"""Query Azure Monitor: Log Analytics (KQL) for logs, Azure Monitor Metrics
for resource metrics. Auth via an AAD service principal. azure-core's own
pipeline retries 429/5xx by default; retry_total/backoff below just make
that explicit and consistent with the other real-source tools.

Logs and metrics are two separate SDK packages as of the 2024+ Azure SDK
layout (`azure-monitor-query` no longer includes a metrics client) --
metrics needs its own regional endpoint, hence AZURE_METRICS_ENDPOINT below."""
import os
from datetime import timedelta

from azure.identity import ClientSecretCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus
from azure.monitor.querymetrics import MetricsClient

import demo_data
import integration_credentials
import users

AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
AZURE_LOG_ANALYTICS_WORKSPACE_ID = os.environ.get("AZURE_LOG_ANALYTICS_WORKSPACE_ID", "")
# Regional endpoint, e.g. https://westeurope.metrics.monitor.azure.com -- must
# match the region of the resources you query metrics for.
AZURE_METRICS_ENDPOINT = os.environ.get("AZURE_METRICS_ENDPOINT", "")


def _config(user_id: int, deployment_id: int | None = None, client_id: int | None = None) -> dict:
    # NOTE: `client_id` here is OUR scoping id (this project's client row);
    # cfg["client_id"]/AZURE_CLIENT_ID below is Azure's own AD app client id
    # -- same name, unrelated concepts.
    override = integration_credentials.resolve_credentials(
        "azure", user_id, deployment_id=deployment_id, client_id=client_id
    ) or {}
    return {
        "tenant_id": override.get("tenant_id") or AZURE_TENANT_ID,
        "client_id": override.get("client_id") or AZURE_CLIENT_ID,
        "client_secret": override.get("client_secret") or AZURE_CLIENT_SECRET,
        "log_analytics_workspace_id": override.get("log_analytics_workspace_id") or AZURE_LOG_ANALYTICS_WORKSPACE_ID,
        "metrics_endpoint": override.get("metrics_endpoint") or AZURE_METRICS_ENDPOINT,
    }


def _credential(user_id: int, deployment_id: int | None = None, client_id: int | None = None):
    cfg = _config(user_id, deployment_id=deployment_id, client_id=client_id)
    return ClientSecretCredential(cfg["tenant_id"], cfg["client_id"], cfg["client_secret"])


def query_logs(kql: str, user_id: int, deployment_id: int | None = None) -> str:
    """Run a KQL query against the configured Log Analytics workspace."""
    cfg = _config(user_id, deployment_id=deployment_id)
    if not (cfg["tenant_id"] and cfg["client_id"] and cfg["client_secret"] and cfg["log_analytics_workspace_id"]):
        if users.get_demo_mode(user_id):
            return demo_data.azure_monitor_logs(kql)
        return "ERROR: Azure credentials/workspace not configured"
    try:
        client = LogsQueryClient(_credential(user_id, deployment_id=deployment_id), retry_total=1, retry_backoff_factor=1.0)
        response = client.query_workspace(
            workspace_id=cfg["log_analytics_workspace_id"],
            query=kql,
            timespan=timedelta(hours=1),
        )
    except Exception as e:
        return f"ERROR querying Azure Log Analytics: {type(e).__name__}: {e}"

    if response.status != LogsQueryStatus.SUCCESS:
        return f"ERROR: Azure query returned status {response.status}: {getattr(response, 'partial_error', '')}"

    lines = []
    for table in response.tables:
        cols = table.columns
        for row in table.rows[:50]:
            lines.append(", ".join(f"{c}={v}" for c, v in zip(cols, row)))
    return "\n".join(lines)[:3000] if lines else "No matching rows found."


def query_metrics(
    resource_id: str, metric_namespace: str, metric_names: str, user_id: int, deployment_id: int | None = None
) -> str:
    """metric_namespace: e.g. 'Microsoft.Compute/virtualMachines'.
    metric_names: comma-separated Azure Monitor metric names, e.g. 'Percentage CPU,Network In'."""
    cfg = _config(user_id, deployment_id=deployment_id)
    if not (cfg["tenant_id"] and cfg["client_id"] and cfg["client_secret"] and cfg["metrics_endpoint"]):
        if users.get_demo_mode(user_id):
            return demo_data.azure_monitor_metrics(resource_id, metric_namespace, metric_names)
        return "ERROR: Azure credentials/metrics endpoint not configured"
    try:
        client = MetricsClient(
            cfg["metrics_endpoint"], _credential(user_id, deployment_id=deployment_id),
            retry_total=1, retry_backoff_factor=1.0,
        )
        results = client.query_resources(
            resource_ids=[resource_id],
            metric_namespace=metric_namespace,
            metric_names=[m.strip() for m in metric_names.split(",")],
            timespan=timedelta(hours=1),
        )
    except Exception as e:
        return f"ERROR querying Azure Monitor metrics: {type(e).__name__}: {e}"

    lines = []
    for result in results:
        for metric in result.metrics:
            for ts in metric.timeseries:
                for point in ts.data[-10:]:
                    lines.append(f"{metric.name} @ {point.timestamp}: avg={point.average}")
    return "\n".join(lines)[:3000] if lines else "No metric data points found."
