import httpx
import respx

import settings
from tools import azure_devops, jira, loki, prometheus, zendesk


@respx.mock
def test_configured_reports_prometheus_unreachable_as_not_configured(monkeypatch):
    """docker-compose.prod.yml doesn't run a local prometheus/loki at all --
    the default URL resolving to *something* isn't the same as it actually
    being reachable."""
    monkeypatch.setattr(prometheus, "_config", lambda user_id, deployment_id=None, client_id=None: {"url": "http://prom.local"})
    respx.get("http://prom.local/-/ready").mock(side_effect=httpx.ConnectError("nope"))

    assert settings._configured(1, "prometheus") is False


@respx.mock
def test_configured_reports_prometheus_reachable_as_configured(monkeypatch):
    monkeypatch.setattr(prometheus, "_config", lambda user_id, deployment_id=None, client_id=None: {"url": "http://prom.local"})
    respx.get("http://prom.local/-/ready").mock(return_value=httpx.Response(200))

    assert settings._configured(1, "prometheus") is True


@respx.mock
def test_configured_reports_loki_unreachable_as_not_configured(monkeypatch):
    monkeypatch.setattr(loki, "_config", lambda user_id, deployment_id=None, client_id=None: {"url": "http://loki.local"})
    respx.get("http://loki.local/ready").mock(side_effect=httpx.ConnectError("nope"))

    assert settings._configured(1, "loki") is False


def test_client_integration_status_reports_own_override(monkeypatch):
    monkeypatch.setattr(settings.integration_credentials, "has_client_override", lambda client_id, user_id, name: name == "jira")
    monkeypatch.setattr(settings.integration_credentials, "has_override", lambda user_id, name: False)
    monkeypatch.setattr(settings, "_client_configured", lambda client_id, user_id, name: True)

    result = settings.client_integration_status(7, 1)
    jira_status = next(r for r in result if r["name"] == "jira")
    assert jira_status["override"] is True
    assert jira_status["using_global_default"] is False


def test_client_integration_status_reports_global_default(monkeypatch):
    monkeypatch.setattr(settings.integration_credentials, "has_client_override", lambda client_id, user_id, name: False)
    monkeypatch.setattr(settings.integration_credentials, "has_override", lambda user_id, name: name == "jira")
    monkeypatch.setattr(settings, "_client_configured", lambda client_id, user_id, name: True)

    result = settings.client_integration_status(7, 1)
    jira_status = next(r for r in result if r["name"] == "jira")
    assert jira_status["override"] is False
    assert jira_status["using_global_default"] is True


def test_set_client_integration_rejects_unknown_integration():
    try:
        settings.set_client_integration(7, 1, "not-a-real-integration", {})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_set_client_integration_drops_unknown_fields(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        settings.integration_credentials, "set_client_credentials",
        lambda client_id, user_id, name, fields: captured.update(client_id=client_id, user_id=user_id, name=name, fields=fields),
    )
    monkeypatch.setattr(settings, "_client_configured", lambda client_id, user_id, name: True)

    settings.set_client_integration(7, 1, "jira", {"api_token": "abc", "not_a_field": "x"})
    assert captured == {"client_id": 7, "user_id": 1, "name": "jira", "fields": {"api_token": "abc"}}


def test_clear_client_integration_delegates(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        settings.integration_credentials, "clear_client_credentials",
        lambda client_id, user_id, name: captured.update(client_id=client_id, user_id=user_id, name=name),
    )
    monkeypatch.setattr(settings, "_client_configured", lambda client_id, user_id, name: False)

    result = settings.clear_client_integration(7, 1, "jira")
    assert captured == {"client_id": 7, "user_id": 1, "name": "jira"}
    assert result["override"] is False


def test_test_client_integration_reports_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "_client_configured", lambda client_id, user_id, name: False)
    result = settings.test_client_integration(7, 1, "jira")
    assert result == {"ok": False, "detail": "not configured"}


def test_client_integration_status_includes_azure_devops(monkeypatch):
    monkeypatch.setattr(settings.integration_credentials, "has_client_override", lambda client_id, user_id, name: False)
    monkeypatch.setattr(settings.integration_credentials, "has_override", lambda user_id, name: False)
    monkeypatch.setattr(settings, "_client_configured", lambda client_id, user_id, name: False)

    result = settings.client_integration_status(7, 1)
    assert any(r["name"] == "azure_devops" for r in result)


def test_test_client_integration_azure_devops_uses_client_scoped_config(monkeypatch):
    from tools import azure_devops

    monkeypatch.setattr(settings, "_client_configured", lambda client_id, user_id, name: True)
    monkeypatch.setattr(
        azure_devops, "_config",
        lambda user_id, deployment_id=None, client_id=None: {"organization": "contoso", "project": "MyProject", "pat": "tok"},
    )

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"authenticatedUser": {"providerDisplayName": "Ops Bot"}}

    monkeypatch.setattr(settings.httpx, "get", lambda *a, **kw: FakeResponse())
    result = settings.test_client_integration(7, 1, "azure_devops")
    assert result["ok"] is True
    assert "Ops Bot" in result["detail"]


def test_test_client_integration_jira_uses_client_scoped_config(monkeypatch):
    monkeypatch.setattr(settings, "_client_configured", lambda client_id, user_id, name: True)
    monkeypatch.setattr(
        jira, "_config",
        lambda user_id, deployment_id=None, client_id=None: {"base_url": "https://x.atlassian.net", "email": "a@b.com", "api_token": "tok"},
    )

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"displayName": "Ops Bot"}

    monkeypatch.setattr(settings.httpx, "get", lambda *a, **kw: FakeResponse())
    result = settings.test_client_integration(7, 1, "jira")
    assert result["ok"] is True
    assert "Ops Bot" in result["detail"]


def test_client_integration_status_includes_zendesk(monkeypatch):
    monkeypatch.setattr(settings.integration_credentials, "has_client_override", lambda client_id, user_id, name: False)
    monkeypatch.setattr(settings.integration_credentials, "has_override", lambda user_id, name: False)
    monkeypatch.setattr(settings, "_client_configured", lambda client_id, user_id, name: False)

    result = settings.client_integration_status(7, 1)
    assert any(r["name"] == "zendesk" for r in result)


def test_test_client_integration_zendesk_uses_client_scoped_config(monkeypatch):
    monkeypatch.setattr(settings, "_client_configured", lambda client_id, user_id, name: True)
    monkeypatch.setattr(
        zendesk, "_config",
        lambda user_id, deployment_id=None, client_id=None: {"subdomain": "acme", "email": "ops@acme.com", "api_token": "tok"},
    )

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"user": {"name": "Ops Bot"}}

    monkeypatch.setattr(settings.httpx, "get", lambda *a, **kw: FakeResponse())
    result = settings.test_client_integration(7, 1, "zendesk")
    assert result["ok"] is True
    assert "Ops Bot" in result["detail"]


def test_client_recent_tickets_aggregates_and_sorts_across_sources(monkeypatch):
    monkeypatch.setattr(
        jira, "list_recent_issues",
        lambda user_id, client_id=None, days=30: [
            {"source": "jira", "id": "OPS-1", "title": "older", "type": "Bug", "status": "Open", "updated": "2026-07-09T00:00:00.000+0000", "url": None},
        ],
    )
    monkeypatch.setattr(
        azure_devops, "list_recent_work_items",
        lambda user_id, client_id=None, days=30: [
            {"source": "azure_devops", "id": 1, "title": "newest", "type": "Bug", "status": "Active", "updated": "2026-07-11T00:00:00Z", "url": None},
        ],
    )
    monkeypatch.setattr(
        zendesk, "list_recent_tickets",
        lambda user_id, client_id=None, days=30: [
            {"source": "zendesk", "id": 1, "title": "middle", "type": "ticket", "status": "open", "updated": "2026-07-10T00:00:00Z", "url": None},
        ],
    )
    result = settings.client_recent_tickets(7, 1)
    assert [r["title"] for r in result] == ["newest", "middle", "older"]


def test_client_recent_tickets_caps_at_thirty(monkeypatch):
    monkeypatch.setattr(
        jira, "list_recent_issues",
        lambda user_id, client_id=None, days=30: [
            {"source": "jira", "id": f"OPS-{i}", "title": "x", "type": "Bug", "status": "Open", "updated": "2026-07-10T00:00:00.000+0000", "url": None}
            for i in range(40)
        ],
    )
    monkeypatch.setattr(azure_devops, "list_recent_work_items", lambda user_id, client_id=None, days=30: [])
    monkeypatch.setattr(zendesk, "list_recent_tickets", lambda user_id, client_id=None, days=30: [])
    assert len(settings.client_recent_tickets(7, 1)) == 30


def test_ticket_sort_key_tolerates_missing_or_malformed_timestamp():
    assert settings._ticket_sort_key({}) == settings._ticket_sort_key({"updated": "not-a-date"})


def test_client_recent_tickets_filters_out_closed_items(monkeypatch):
    monkeypatch.setattr(
        jira, "list_recent_issues",
        lambda user_id, client_id=None, days=30: [
            {"source": "jira", "id": "OPS-1", "title": "still open", "type": "Bug", "status": "In Progress", "updated": "2026-07-10T00:00:00.000+0000", "url": None},
            {"source": "jira", "id": "OPS-2", "title": "wrapped up", "type": "Bug", "status": "Done", "updated": "2026-07-11T00:00:00.000+0000", "url": None},
        ],
    )
    monkeypatch.setattr(
        azure_devops, "list_recent_work_items",
        lambda user_id, client_id=None, days=30: [
            {"source": "azure_devops", "id": 1, "title": "shipped fix", "type": "Bug", "status": "Closed", "updated": "2026-07-11T00:00:00Z", "url": None},
        ],
    )
    monkeypatch.setattr(
        zendesk, "list_recent_tickets",
        lambda user_id, client_id=None, days=30: [
            {"source": "zendesk", "id": 1, "title": "customer happy", "type": "ticket", "status": "solved", "updated": "2026-07-11T00:00:00Z", "url": None},
        ],
    )
    result = settings.client_recent_tickets(7, 1)
    assert [r["title"] for r in result] == ["still open"]
