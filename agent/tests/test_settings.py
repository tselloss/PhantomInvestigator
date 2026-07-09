import settings
from tools import jira


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
