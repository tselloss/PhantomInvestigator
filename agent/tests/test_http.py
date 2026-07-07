import httpx
import pytest
import respx

from tools._http import request_with_retry


@respx.mock
def test_retries_once_on_503_then_succeeds(monkeypatch):
    monkeypatch.setattr("tools._http.time.sleep", lambda s: None)
    route = respx.get("https://example.com/x").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})]
    )
    resp = request_with_retry("GET", "https://example.com/x")
    assert resp.status_code == 200
    assert route.call_count == 2


@respx.mock
def test_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr("tools._http.time.sleep", lambda s: None)
    route = respx.get("https://example.com/x").mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        request_with_retry("GET", "https://example.com/x")
    assert route.call_count == 2  # initial attempt + 1 retry


@respx.mock
def test_no_retry_on_non_retryable_status():
    route = respx.get("https://example.com/x").mock(return_value=httpx.Response(404))
    with pytest.raises(httpx.HTTPStatusError):
        request_with_retry("GET", "https://example.com/x")
    assert route.call_count == 1
