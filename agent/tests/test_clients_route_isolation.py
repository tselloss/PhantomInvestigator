"""End-to-end isolation check through the real route + real clients.py
module (only the DB connection is faked) -- proves a logged-in user genuinely
cannot reach another user's client via the API, not just that a mock was
configured to return None."""
from fastapi.testclient import TestClient

import main
from routes import clients as clients_route
from tests.test_clients_isolation import _FakeConn


def _login_as(monkeypatch, user_id: int):
    monkeypatch.setattr(main, "verify_session_cookie", lambda token: {"user_id": user_id, "username": f"user-{user_id}"})


def test_user_cannot_fetch_another_users_client_via_the_api(monkeypatch):
    table = {}
    monkeypatch.setattr(clients_route.store, "_connect", lambda: _FakeConn(table))
    client = TestClient(main.app)

    _login_as(monkeypatch, 1)
    created = client.post("/api/clients", json={"name": "Acme Corp", "slug": "acme-corp"}).json()

    _login_as(monkeypatch, 2)
    resp = client.get(f"/api/clients/{created['id']}")

    assert resp.status_code == 404


def test_user_only_sees_their_own_clients_in_the_list(monkeypatch):
    table = {}
    monkeypatch.setattr(clients_route.store, "_connect", lambda: _FakeConn(table))
    client = TestClient(main.app)

    _login_as(monkeypatch, 1)
    client.post("/api/clients", json={"name": "Acme Corp", "slug": "acme-corp"})

    _login_as(monkeypatch, 2)
    client.post("/api/clients", json={"name": "Widgets Inc", "slug": "widgets-inc"})
    resp = client.get("/api/clients")

    assert resp.status_code == 200
    assert [c["name"] for c in resp.json()] == ["Widgets Inc"]
