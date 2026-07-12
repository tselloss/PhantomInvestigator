import datetime
from unittest.mock import MagicMock, patch

from tools import aws_cloudwatch as aws


def _configure(monkeypatch):
    monkeypatch.setattr(aws, "AWS_ACCESS_KEY_ID", "id")
    monkeypatch.setattr(aws, "AWS_SECRET_ACCESS_KEY", "secret")


def test_query_logs_requires_credentials(monkeypatch):
    monkeypatch.setattr(aws, "AWS_ACCESS_KEY_ID", "")
    assert aws.query_logs("group", "pattern", 1).startswith("ERROR")


def test_query_logs_formats_events(monkeypatch):
    _configure(monkeypatch)
    fake_logs_client = MagicMock()
    fake_logs_client.filter_log_events.return_value = {"events": [{"message": "OOM killed process"}]}

    with patch.object(aws, "_client", return_value=fake_logs_client):
        result = aws.query_logs("my-log-group", "ERROR", 1)

    assert "OOM killed process" in result
    assert "untrusted data" in result


def test_query_logs_no_events(monkeypatch):
    _configure(monkeypatch)
    fake_logs_client = MagicMock()
    fake_logs_client.filter_log_events.return_value = {"events": []}

    with patch.object(aws, "_client", return_value=fake_logs_client):
        result = aws.query_logs("my-log-group", "ERROR", 1)

    assert result == "No matching log events found."


def test_query_logs_handles_exception(monkeypatch):
    _configure(monkeypatch)
    with patch.object(aws, "_client", side_effect=RuntimeError("boom")):
        result = aws.query_logs("my-log-group", "ERROR", 1)
    assert result.startswith("ERROR")


def test_query_metrics_requires_credentials(monkeypatch):
    monkeypatch.setattr(aws, "AWS_ACCESS_KEY_ID", "")
    assert aws.query_metrics("AWS/EC2", "CPUUtilization", 1).startswith("ERROR")


def test_query_metrics_invalid_dimensions_json(monkeypatch):
    _configure(monkeypatch)
    result = aws.query_metrics("AWS/EC2", "CPUUtilization", 1, dimensions_json="not-json")
    assert result.startswith("ERROR")


def test_query_metrics_formats_datapoints(monkeypatch):
    _configure(monkeypatch)
    fake_cw_client = MagicMock()
    fake_cw_client.get_metric_statistics.return_value = {
        "Datapoints": [{"Timestamp": datetime.datetime(2026, 7, 1), "Average": 55.0, "Maximum": 80.0}]
    }

    with patch.object(aws, "_client", return_value=fake_cw_client):
        result = aws.query_metrics("AWS/EC2", "CPUUtilization", 1)

    assert "avg=55.0" in result
    assert "max=80.0" in result


def test_query_metrics_no_datapoints(monkeypatch):
    _configure(monkeypatch)
    fake_cw_client = MagicMock()
    fake_cw_client.get_metric_statistics.return_value = {"Datapoints": []}

    with patch.object(aws, "_client", return_value=fake_cw_client):
        result = aws.query_metrics("AWS/EC2", "CPUUtilization", 1)

    assert result == "No metric data points found."


def test_client_forwards_scoping_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured.update(deployment_id=deployment_id, client_id=client_id)
        return {"access_key_id": "id", "secret_access_key": "secret", "region": "us-east-1"}

    monkeypatch.setattr(aws, "_config", fake_config)
    with patch("boto3.client"):
        aws._client("logs", 1, deployment_id=42, client_id=7)
    assert captured == {"deployment_id": 42, "client_id": 7}


def test_query_logs_passes_deployment_id_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["deployment_id"] = deployment_id
        return {"access_key_id": "", "secret_access_key": "", "region": "us-east-1"}

    monkeypatch.setattr(aws, "_config", fake_config)
    aws.query_logs("group", "pattern", 1, deployment_id=42)
    assert captured["deployment_id"] == 42


def test_query_metrics_passes_deployment_id_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["deployment_id"] = deployment_id
        return {"access_key_id": "", "secret_access_key": "", "region": "us-east-1"}

    monkeypatch.setattr(aws, "_config", fake_config)
    aws.query_metrics("AWS/EC2", "CPUUtilization", 1, deployment_id=42)
    assert captured["deployment_id"] == 42
