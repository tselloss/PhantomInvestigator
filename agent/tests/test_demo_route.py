import httpx
import pytest
import respx
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def bypass_auth(monkeypatch):
    """/api/* is session-gated by main.AuthMiddleware; these tests exercise
    the demo routes themselves, not the login flow, so bypass it the same
    way a valid session cookie would (see test_clients_route.py)."""
    monkeypatch.setattr(main, "verify_session_cookie", lambda token: {"user_id": 1, "username": "test-operator"})


client = TestClient(main.app)


@respx.mock
def test_demo_health_proxies_active_faults(monkeypatch):
    monkeypatch.setattr(main, "DEMO_APP_URL", "http://demo-app-test:8000")
    respx.get("http://demo-app-test:8000/health").mock(
        return_value=httpx.Response(200, json={"ok": True, "active_faults": ["slow_db"]})
    )
    resp = client.get("/api/demo/health")
    assert resp.status_code == 200
    assert resp.json()["active_faults"] == ["slow_db"]


@respx.mock
def test_demo_checkout_test_reports_status_and_latency(monkeypatch):
    monkeypatch.setattr(main, "DEMO_APP_URL", "http://demo-app-test:8000")
    respx.post("http://demo-app-test:8000/checkout").mock(
        return_value=httpx.Response(200, json={"order_id": 1, "status": "confirmed"})
    )
    resp = client.post("/api/demo/checkout-test?count=3")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 3
    for r in results:
        assert r["status_code"] == 200
        assert r["latency_ms"] >= 0


@respx.mock
def test_demo_checkout_test_reports_fault_error_codes(monkeypatch):
    monkeypatch.setattr(main, "DEMO_APP_URL", "http://demo-app-test:8000")
    respx.post("http://demo-app-test:8000/checkout").mock(return_value=httpx.Response(502, json={"detail": "payment provider timeout"}))
    resp = client.post("/api/demo/checkout-test?count=1")
    assert resp.json()["results"][0]["status_code"] == 502


def test_demo_checkout_test_clamps_count(monkeypatch):
    monkeypatch.setattr(main, "DEMO_APP_URL", "http://demo-app-test:8000")
    with respx.mock:
        respx.post("http://demo-app-test:8000/checkout").mock(return_value=httpx.Response(200, json={}))
        resp = client.post("/api/demo/checkout-test?count=999")
    assert len(resp.json()["results"]) == 20  # clamped, not 999


@respx.mock
def test_demo_checkout_test_handles_unreachable_app(monkeypatch):
    monkeypatch.setattr(main, "DEMO_APP_URL", "http://demo-app-test:8000")
    respx.post("http://demo-app-test:8000/checkout").mock(side_effect=httpx.ConnectError("refused"))
    resp = client.post("/api/demo/checkout-test?count=1")
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["status_code"] is None
    assert "error" in result
