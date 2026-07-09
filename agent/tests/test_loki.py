import httpx
import respx

from tools import loki


@respx.mock
def test_search_formats_log_lines(monkeypatch):
    monkeypatch.setattr(loki, "LOKI_URL", "http://loki.local")
    respx.get("http://loki.local/loki/api/v1/query_range").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"result": [{"values": [["1234567890", "ERROR pool exhausted"]]}]}},
        )
    )
    result = loki.search('{container="app"} |= "error"', 1)
    assert "ERROR pool exhausted" in result
    assert "untrusted data" in result


@respx.mock
def test_search_no_matching_lines(monkeypatch):
    monkeypatch.setattr(loki, "LOKI_URL", "http://loki.local")
    respx.get("http://loki.local/loki/api/v1/query_range").mock(
        return_value=httpx.Response(200, json={"data": {"result": []}})
    )
    result = loki.search('{container="app"}', 1)
    assert result == "No matching log lines found."


@respx.mock
def test_search_handles_http_error(monkeypatch):
    monkeypatch.setattr(loki, "LOKI_URL", "http://loki.local")
    respx.get("http://loki.local/loki/api/v1/query_range").mock(return_value=httpx.Response(500))
    result = loki.search('{container="app"}', 1)
    assert result.startswith("ERROR")


def test_search_passes_deployment_id_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["deployment_id"] = deployment_id
        return {"url": "http://loki.local"}

    monkeypatch.setattr(loki, "_config", fake_config)
    with respx.mock:
        respx.get("http://loki.local/loki/api/v1/query_range").mock(
            return_value=httpx.Response(200, json={"data": {"result": []}})
        )
        loki.search('{container="app"}', 1, deployment_id=42)
    assert captured["deployment_id"] == 42
