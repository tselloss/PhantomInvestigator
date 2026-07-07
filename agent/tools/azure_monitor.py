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

AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
AZURE_LOG_ANALYTICS_WORKSPACE_ID = os.environ.get("AZURE_LOG_ANALYTICS_WORKSPACE_ID", "")
# Regional endpoint, e.g. https://westeurope.metrics.monitor.azure.com -- must
# match the region of the resources you query metrics for.
AZURE_METRICS_ENDPOINT = os.environ.get("AZURE_METRICS_ENDPOINT", "")


def _credential():
    return ClientSecretCredential(AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET)


def query_logs(kql: str) -> str:
    """Run a KQL query against the configured Log Analytics workspace."""
    if not (AZURE_TENANT_ID and AZURE_CLIENT_ID and AZURE_CLIENT_SECRET and AZURE_LOG_ANALYTICS_WORKSPACE_ID):
        return "ERROR: Azure credentials/workspace not configured"
    try:
        client = LogsQueryClient(_credential(), retry_total=1, retry_backoff_factor=1.0)
        response = client.query_workspace(
            workspace_id=AZURE_LOG_ANALYTICS_WORKSPACE_ID,
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


def query_metrics(resource_id: str, metric_namespace: str, metric_names: str) -> str:
    """metric_namespace: e.g. 'Microsoft.Compute/virtualMachines'.
    metric_names: comma-separated Azure Monitor metric names, e.g. 'Percentage CPU,Network In'."""
    if not (AZURE_TENANT_ID and AZURE_CLIENT_ID and AZURE_CLIENT_SECRET and AZURE_METRICS_ENDPOINT):
        return "ERROR: Azure credentials/metrics endpoint not configured"
    try:
        client = MetricsClient(AZURE_METRICS_ENDPOINT, _credential(), retry_total=1, retry_backoff_factor=1.0)
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
