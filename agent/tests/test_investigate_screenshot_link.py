from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import loop
import main


@pytest.fixture(autouse=True)
def bypass_auth(monkeypatch):
    monkeypatch.setattr(main, "verify_session_cookie", lambda token: {"user_id": 1, "username": "test-operator"})


@pytest.fixture(autouse=True)
def no_duplicate(monkeypatch):
    monkeypatch.setattr(main.investigations, "find_recent_duplicate", lambda *a, **kw: None)


client = TestClient(main.app)


def test_investigate_links_screenshot_when_id_provided(monkeypatch):
    monkeypatch.setattr(main.investigations, "start", lambda *a, **kw: 55)
    monkeypatch.setattr(main.investigations, "finish", lambda *a, **kw: None)

    with patch.object(main.screenshots, "link_to_investigation") as mock_link, \
         patch.object(loop, "run_agent", return_value={"postmortem": None}):
        resp = client.post("/api/investigate", json={"alert": "checkout down", "screenshot_id": 7})

    assert resp.status_code == 200
    mock_link.assert_called_once_with(7, 55)


def test_investigate_skips_link_without_screenshot_id(monkeypatch):
    monkeypatch.setattr(main.investigations, "start", lambda *a, **kw: 56)
    monkeypatch.setattr(main.investigations, "finish", lambda *a, **kw: None)

    with patch.object(main.screenshots, "link_to_investigation") as mock_link, \
         patch.object(loop, "run_agent", return_value={"postmortem": None}):
        resp = client.post("/api/investigate", json={"alert": "checkout down"})

    assert resp.status_code == 200
    mock_link.assert_not_called()


def test_investigate_includes_deployment_note_for_model(monkeypatch):
    monkeypatch.setattr(main.investigations, "start", lambda *a, **kw: 61)
    monkeypatch.setattr(main.investigations, "finish", lambda *a, **kw: None)
    monkeypatch.setattr(main.clients, "get_deployment", lambda deployment_id, owner_user_id: {"id": 42, "client_id": 7, "label": "prod"})
    monkeypatch.setattr(main.clients, "get_client", lambda client_id, owner_user_id: {"id": 7, "name": "Acme Corp"})
    monkeypatch.setattr(main.clients, "is_black_box", lambda deployment_id, owner_user_id: False)

    with patch.object(loop, "run_agent", return_value={"postmortem": None}) as mock_run:
        resp = client.post("/api/investigate", json={"alert": "checkout down", "deployment_id": 42})

    assert resp.status_code == 200
    called_alert = mock_run.call_args.args[0]
    assert "Acme Corp / prod (id 42)" in called_alert
    assert "checkout down" in called_alert


def test_investigate_omits_deployment_note_without_deployment_id(monkeypatch):
    monkeypatch.setattr(main.investigations, "start", lambda *a, **kw: 62)
    monkeypatch.setattr(main.investigations, "finish", lambda *a, **kw: None)

    with patch.object(loop, "run_agent", return_value={"postmortem": None}) as mock_run:
        resp = client.post("/api/investigate", json={"alert": "checkout down"})

    assert resp.status_code == 200
    assert mock_run.call_args.args[0] == "checkout down"


def test_investigate_stream_links_screenshot_when_id_provided(monkeypatch):
    monkeypatch.setattr(main.investigations, "start", lambda *a, **kw: 60)
    monkeypatch.setattr(main.investigations, "finish", lambda *a, **kw: None)

    def fake_stream(alert_text, owner_user_id, deployment_id=None):
        yield {"type": "final", "data": {"postmortem": None}}

    with patch.object(main.screenshots, "link_to_investigation") as mock_link, \
         patch.object(loop, "run_agent_stream", side_effect=fake_stream):
        resp = client.get("/api/investigate/stream", params={"alert": "checkout down", "screenshot_id": 9})

    assert resp.status_code == 200
    mock_link.assert_called_once_with(9, 60)


def test_investigate_returns_deduped_response_without_running_agent(monkeypatch):
    existing = {"id": 40, "result": {"postmortem": None, "usage": {"cost_usd": 0.01}}}
    monkeypatch.setattr(main.investigations, "find_recent_duplicate", lambda *a, **kw: existing)
    monkeypatch.setattr(main.investigations, "start", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not start a new investigation")))

    with patch.object(loop, "run_agent") as mock_run:
        resp = client.post("/api/investigate", json={"alert": "checkout down"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["deduped"] is True
    assert body["investigation_id"] == 40
    mock_run.assert_not_called()


def test_investigate_stream_returns_deduped_final_event_without_running_agent(monkeypatch):
    existing = {"id": 41, "result": {"postmortem": None}}
    monkeypatch.setattr(main.investigations, "find_recent_duplicate", lambda *a, **kw: existing)
    monkeypatch.setattr(main.investigations, "start", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not start a new investigation")))

    with patch.object(loop, "run_agent_stream") as mock_stream:
        resp = client.get("/api/investigate/stream", params={"alert": "checkout down"})

    assert resp.status_code == 200
    assert '"deduped": true' in resp.text
    mock_stream.assert_not_called()
