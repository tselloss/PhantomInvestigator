import httpx
import respx

from tools import prometheus


@respx.mock
def test_query_returns_response_body(monkeypatch):
    monkeypatch.setattr(prometheus, "PROMETHEUS_URL", "http://prom.local")
    respx.get("http://prom.local/api/v1/query").mock(
        return_value=httpx.Response(200, json={"status": "success", "data": {"result": []}})
    )
    result = prometheus.query("up", 1)
    assert "success" in result


@respx.mock
def test_query_handles_http_error(monkeypatch):
    monkeypatch.setattr(prometheus, "PROMETHEUS_URL", "http://prom.local")
    respx.get("http://prom.local/api/v1/query").mock(return_value=httpx.Response(500))
    result = prometheus.query("up", 1)
    assert result.startswith("ERROR")


def test_query_passes_deployment_id_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["deployment_id"] = deployment_id
        return {"url": "http://prom.local"}

    monkeypatch.setattr(prometheus, "_config", fake_config)
    with respx.mock:
        respx.get("http://prom.local/api/v1/query").mock(return_value=httpx.Response(200, json={}))
        prometheus.query("up", 1, deployment_id=42)
    assert captured["deployment_id"] == 42
