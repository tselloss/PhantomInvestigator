from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def bypass_auth(monkeypatch):
    """/api/* is session-gated by main.AuthMiddleware; these tests exercise
    the screenshot intake route itself, not the login flow."""
    monkeypatch.setattr(main, "verify_session_cookie", lambda token: {"user_id": 1, "username": "test-operator"})
    monkeypatch.setattr(main, "user_tos_accepted", lambda user_id: True)


client = TestClient(main.app)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def test_upload_rejects_non_image_content_type():
    resp = client.post(
        "/api/investigate/screenshot",
        files={"file": ("notes.txt", b"just text", "text/plain")},
    )
    assert resp.status_code == 415


def test_upload_rejects_oversized_file_without_calling_vision():
    with patch.object(main.vision, "describe_screenshot") as mock_vision:
        resp = client.post(
            "/api/investigate/screenshot",
            files={"file": ("big.png", b"0" * (main.MAX_SCREENSHOT_BYTES + 1), "image/png")},
        )
    assert resp.status_code == 413
    mock_vision.assert_not_called()


def test_upload_happy_path_no_deployment(monkeypatch):
    monkeypatch.setattr(main.vision, "describe_screenshot", lambda data, content_type, user_id: "Error: 500 on checkout page")
    with patch.object(main.screenshots, "store_screenshot", return_value={"id": 1, "filename": "shot.png"}) as mock_store:
        resp = client.post(
            "/api/investigate/screenshot",
            files={"file": ("shot.png", PNG_BYTES, "image/png")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["vision_status"] == "ok"
    assert body["vision_description"] == "Error: 500 on checkout page"
    mock_store.assert_called_once()


def test_upload_vision_failure_still_stores_screenshot(monkeypatch):
    def _raise(data, content_type, user_id):
        raise TimeoutError("vision call timed out")

    monkeypatch.setattr(main.vision, "describe_screenshot", _raise)
    with patch.object(main.screenshots, "store_screenshot", return_value={"id": 2, "filename": "shot.png"}) as mock_store:
        resp = client.post(
            "/api/investigate/screenshot",
            files={"file": ("shot.png", PNG_BYTES, "image/png")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["vision_status"] == "failed"
    assert body["vision_description"] is None
    assert mock_store.call_args.kwargs["vision_status"] == "failed"
    assert mock_store.call_args.kwargs["vision_description"] is None


def test_upload_with_deployment_records_diagnostic_bundle_excerpt(monkeypatch):
    monkeypatch.setattr(main.vision, "describe_screenshot", lambda data, content_type, user_id: "Visible 502 error banner")
    with patch.object(main.screenshots, "store_screenshot", return_value={"id": 3, "filename": "shot.png"}), \
         patch.object(main.diagnostics, "store_bundle") as mock_bundle:
        resp = client.post(
            "/api/investigate/screenshot",
            data={"deployment_id": 42},
            files={"file": ("shot.png", PNG_BYTES, "image/png")},
        )
    assert resp.status_code == 200
    mock_bundle.assert_called_once_with(42, 1, "shot.png", screenshot_excerpt="Visible 502 error banner")


def test_upload_without_deployment_does_not_touch_diagnostic_bundle(monkeypatch):
    monkeypatch.setattr(main.vision, "describe_screenshot", lambda data, content_type, user_id: "Visible 502 error banner")
    with patch.object(main.screenshots, "store_screenshot", return_value={"id": 4, "filename": "shot.png"}), \
         patch.object(main.diagnostics, "store_bundle") as mock_bundle:
        resp = client.post(
            "/api/investigate/screenshot",
            files={"file": ("shot.png", PNG_BYTES, "image/png")},
        )
    assert resp.status_code == 200
    mock_bundle.assert_not_called()
