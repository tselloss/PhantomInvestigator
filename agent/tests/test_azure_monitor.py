from unittest.mock import MagicMock, patch

from azure.monitor.query import LogsQueryStatus

from tools import azure_monitor as az


def _configure(monkeypatch, workspace=True):
    monkeypatch.setattr(az, "AZURE_TENANT_ID", "tid")
    monkeypatch.setattr(az, "AZURE_CLIENT_ID", "cid")
    monkeypatch.setattr(az, "AZURE_CLIENT_SECRET", "secret")
    monkeypatch.setattr(az, "AZURE_LOG_ANALYTICS_WORKSPACE_ID", "wsid" if workspace else "")


def test_query_logs_requires_config(monkeypatch):
    _configure(monkeypatch, workspace=False)
    assert az.query_logs("Traces | take 5", 1).startswith("ERROR")


def test_query_logs_returns_demo_data_when_demo_mode_enabled(monkeypatch):
    _configure(monkeypatch, workspace=False)
    monkeypatch.setattr(az.users, "get_demo_mode", lambda user_id: True)
    result = az.query_logs("Traces | take 5", 1)
    assert "DEMO DATA" in result


def test_query_logs_formats_rows(monkeypatch):
    _configure(monkeypatch)

    fake_table = MagicMock()
    fake_table.columns = ["TimeGenerated", "Message"]
    fake_table.rows = [["2026-07-01T00:00:00Z", "checkout failed"]]
    fake_response = MagicMock()
    fake_response.status = LogsQueryStatus.SUCCESS
    fake_response.tables = [fake_table]

    with patch.object(az, "LogsQueryClient") as MockClient:
        MockClient.return_value.query_workspace.return_value = fake_response
        result = az.query_logs("Traces | take 5", 1)

    assert "checkout failed" in result


def test_query_logs_handles_non_success_status(monkeypatch):
    _configure(monkeypatch)
    fake_response = MagicMock()
    fake_response.status = "not-success"  # anything != LogsQueryStatus.SUCCESS

    with patch.object(az, "LogsQueryClient") as MockClient:
        MockClient.return_value.query_workspace.return_value = fake_response
        result = az.query_logs("Traces | take 5", 1)

    assert result.startswith("ERROR")


def test_query_logs_handles_sdk_exception(monkeypatch):
    _configure(monkeypatch)
    with patch.object(az, "LogsQueryClient", side_effect=RuntimeError("boom")):
        result = az.query_logs("Traces | take 5", 1)
    assert result.startswith("ERROR")


def test_query_metrics_requires_config(monkeypatch):
    monkeypatch.setattr(az, "AZURE_TENANT_ID", "")
    assert az.query_metrics("/subscriptions/x", "Microsoft.Compute/virtualMachines", "Percentage CPU", 1).startswith("ERROR")


def test_query_metrics_returns_demo_data_when_demo_mode_enabled(monkeypatch):
    monkeypatch.setattr(az, "AZURE_TENANT_ID", "")
    monkeypatch.setattr(az.users, "get_demo_mode", lambda user_id: True)
    result = az.query_metrics("/subscriptions/x", "Microsoft.Compute/virtualMachines", "Percentage CPU", 1)
    assert "DEMO DATA" in result


def test_query_metrics_requires_endpoint(monkeypatch):
    monkeypatch.setattr(az, "AZURE_TENANT_ID", "tid")
    monkeypatch.setattr(az, "AZURE_CLIENT_ID", "cid")
    monkeypatch.setattr(az, "AZURE_CLIENT_SECRET", "secret")
    monkeypatch.setattr(az, "AZURE_METRICS_ENDPOINT", "")
    assert az.query_metrics("/subscriptions/x", "Microsoft.Compute/virtualMachines", "Percentage CPU", 1).startswith("ERROR")


def test_query_metrics_formats_points(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(az, "AZURE_METRICS_ENDPOINT", "https://westeurope.metrics.monitor.azure.com")

    point = MagicMock(timestamp="2026-07-01T00:00:00Z", average=42.0)
    ts = MagicMock(data=[point])
    metric = MagicMock(timeseries=[ts])
    metric.name = "Percentage CPU"
    fake_result = MagicMock(metrics=[metric])

    with patch.object(az, "MetricsClient") as MockClient:
        MockClient.return_value.query_resources.return_value = [fake_result]
        result = az.query_metrics(
            "/subscriptions/x/resourceGroups/y", "Microsoft.Compute/virtualMachines", "Percentage CPU", 1
        )

    assert "Percentage CPU" in result
    assert "42.0" in result


def test_credential_forwards_scoping_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured.update(deployment_id=deployment_id, client_id=client_id)
        return {"tenant_id": "tid", "client_id": "cid", "client_secret": "secret"}

    monkeypatch.setattr(az, "_config", fake_config)
    az._credential(1, deployment_id=42, client_id=7)
    assert captured == {"deployment_id": 42, "client_id": 7}


def test_query_logs_passes_deployment_id_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["deployment_id"] = deployment_id
        return {"tenant_id": "", "client_id": "", "client_secret": "", "log_analytics_workspace_id": ""}

    monkeypatch.setattr(az, "_config", fake_config)
    az.query_logs("Traces | take 5", 1, deployment_id=42)
    assert captured["deployment_id"] == 42


def test_query_metrics_passes_deployment_id_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["deployment_id"] = deployment_id
        return {"tenant_id": "", "client_id": "", "client_secret": "", "metrics_endpoint": ""}

    monkeypatch.setattr(az, "_config", fake_config)
    az.query_metrics("/subscriptions/x", "Microsoft.Compute/virtualMachines", "Percentage CPU", 1, deployment_id=42)
    assert captured["deployment_id"] == 42
