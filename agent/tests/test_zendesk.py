import httpx
import respx

from tools import zendesk


def _configure(monkeypatch):
    monkeypatch.setattr(zendesk, "ZENDESK_SUBDOMAIN", "acme")
    monkeypatch.setattr(zendesk, "ZENDESK_EMAIL", "ops@acme.com")
    monkeypatch.setattr(zendesk, "ZENDESK_API_TOKEN", "tok")


def test_search_tickets_requires_config(monkeypatch):
    monkeypatch.setattr(zendesk, "ZENDESK_SUBDOMAIN", "")
    assert zendesk.search_tickets("checkout", 1).startswith("ERROR")


def test_search_tickets_returns_demo_data_when_demo_mode_enabled(monkeypatch):
    monkeypatch.setattr(zendesk, "ZENDESK_SUBDOMAIN", "")
    monkeypatch.setattr(zendesk.users, "get_demo_mode", lambda user_id: True)
    result = zendesk.search_tickets("checkout", 1)
    assert "DEMO DATA" in result
    assert "checkout" in result


@respx.mock
def test_search_tickets_formats_results(monkeypatch):
    _configure(monkeypatch)
    respx.get("https://acme.zendesk.com/api/v2/search.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 10482,
                        "status": "open",
                        "subject": "Checkout keeps failing",
                        "created_at": "2026-07-10T14:13:02Z",
                        "description": "I keep getting an error at checkout.",
                    }
                ]
            },
        )
    )
    result = zendesk.search_tickets("checkout", 1)
    assert "#10482" in result
    assert "Checkout keeps failing" in result
    assert "open" in result


@respx.mock
def test_search_tickets_no_results(monkeypatch):
    _configure(monkeypatch)
    respx.get("https://acme.zendesk.com/api/v2/search.json").mock(return_value=httpx.Response(200, json={"results": []}))
    assert zendesk.search_tickets("checkout", 1) == "No matching support tickets found."


@respx.mock
def test_search_tickets_handles_http_error(monkeypatch):
    _configure(monkeypatch)
    respx.get("https://acme.zendesk.com/api/v2/search.json").mock(return_value=httpx.Response(500))
    result = zendesk.search_tickets("checkout", 1)
    assert result.startswith("ERROR")


def test_search_tickets_passes_deployment_id_to_config(monkeypatch):
    captured = {}

    def fake_config(user_id, deployment_id=None, client_id=None):
        captured["deployment_id"] = deployment_id
        return {"subdomain": "", "email": "", "api_token": ""}

    monkeypatch.setattr(zendesk, "_config", fake_config)
    zendesk.search_tickets("checkout", 1, deployment_id=42)
    assert captured["deployment_id"] == 42
