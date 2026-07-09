import settings


def test_get_ai_provider_status_not_configured(monkeypatch):
    monkeypatch.setattr(settings.providers, "resolve_ai_config", lambda user_id: {"provider": "anthropic", "api_key": "", "model": "x", "base_url": ""})
    monkeypatch.setattr(settings.integration_credentials, "has_override", lambda user_id, name: False)

    status = settings.get_ai_provider_status(1)
    assert status == {"configured": False, "provider": "anthropic", "override": False}


def test_get_ai_provider_status_configured_via_override(monkeypatch):
    monkeypatch.setattr(settings.providers, "resolve_ai_config", lambda user_id: {"provider": "openai", "api_key": "sk-x", "model": "gpt-4o-mini", "base_url": ""})
    monkeypatch.setattr(settings.integration_credentials, "has_override", lambda user_id, name: name == "ai")

    status = settings.get_ai_provider_status(1)
    assert status == {"configured": True, "provider": "openai", "override": True}


def test_set_ai_provider_drops_unknown_fields(monkeypatch):
    captured = {}
    monkeypatch.setattr(settings.integration_credentials, "set_credentials", lambda user_id, name, fields: captured.update(user_id=user_id, name=name, fields=fields))
    monkeypatch.setattr(settings, "get_ai_provider_status", lambda user_id: {"configured": True, "provider": "anthropic", "override": True})

    settings.set_ai_provider(1, {"api_key": "sk-x", "not_a_field": "x"})
    assert captured == {"user_id": 1, "name": "ai", "fields": {"api_key": "sk-x"}}


def test_clear_ai_provider_delegates(monkeypatch):
    captured = {}
    monkeypatch.setattr(settings.integration_credentials, "clear_credentials", lambda user_id, name: captured.update(user_id=user_id, name=name))
    monkeypatch.setattr(settings, "get_ai_provider_status", lambda user_id: {"configured": False, "provider": "anthropic", "override": False})

    result = settings.clear_ai_provider(1)
    assert captured == {"user_id": 1, "name": "ai"}
    assert result["override"] is False


def test_test_ai_provider_reports_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "get_ai_provider_status", lambda user_id: {"configured": False, "provider": "anthropic", "override": False})
    assert settings.test_ai_provider(1) == {"ok": False, "detail": "not configured"}


def test_test_ai_provider_reports_success(monkeypatch):
    monkeypatch.setattr(settings, "get_ai_provider_status", lambda user_id: {"configured": True, "provider": "anthropic", "override": True})

    class FakeProvider:
        def test(self):
            pass

    monkeypatch.setattr(settings.providers, "get_provider", lambda user_id: FakeProvider())
    result = settings.test_ai_provider(1)
    assert result == {"ok": True, "detail": "anthropic key valid"}


def test_test_ai_provider_reports_failure(monkeypatch):
    monkeypatch.setattr(settings, "get_ai_provider_status", lambda user_id: {"configured": True, "provider": "anthropic", "override": True})

    class FakeProvider:
        def test(self):
            raise RuntimeError("bad key")

    monkeypatch.setattr(settings.providers, "get_provider", lambda user_id: FakeProvider())
    result = settings.test_ai_provider(1)
    assert result == {"ok": False, "detail": "RuntimeError: bad key"}
