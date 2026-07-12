import providers


def _clear_ai_env(monkeypatch):
    for var in ("AI_PROVIDER", "AI_API_KEY", "AI_MODEL", "AI_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"):
        monkeypatch.delenv(var, raising=False)


def test_resolve_ai_config_defaults_to_anthropic_with_legacy_env_fallback(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setattr(providers.integration_credentials, "get_credentials", lambda user_id, name: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-legacy")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

    cfg = providers.resolve_ai_config(1)
    assert cfg == {"provider": "anthropic", "api_key": "sk-ant-legacy", "model": "claude-haiku-4-5", "base_url": ""}


def test_resolve_ai_config_prefers_generic_ai_env_over_legacy(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setattr(providers.integration_credentials, "get_credentials", lambda user_id, name: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-legacy")
    monkeypatch.setenv("AI_API_KEY", "sk-ant-new")

    cfg = providers.resolve_ai_config(1)
    assert cfg["api_key"] == "sk-ant-new"


def test_resolve_ai_config_openai_provider_gets_own_default_model(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setattr(providers.integration_credentials, "get_credentials", lambda user_id, name: None)
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "sk-oai")

    cfg = providers.resolve_ai_config(1)
    assert cfg == {"provider": "openai", "api_key": "sk-oai", "model": "gpt-4o-mini", "base_url": ""}


def test_resolve_ai_config_db_override_wins_over_env(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
    monkeypatch.setattr(
        providers.integration_credentials, "get_credentials",
        lambda user_id, name: {"provider": "openai_compatible", "api_key": "sk-override", "model": "custom-model", "base_url": "https://example.com/v1"},
    )

    cfg = providers.resolve_ai_config(1)
    assert cfg == {"provider": "openai_compatible", "api_key": "sk-override", "model": "custom-model", "base_url": "https://example.com/v1"}


def test_resolve_ai_config_no_key_configured_anywhere(monkeypatch):
    _clear_ai_env(monkeypatch)
    monkeypatch.setattr(providers.integration_credentials, "get_credentials", lambda user_id, name: None)

    cfg = providers.resolve_ai_config(1)
    assert cfg["api_key"] == ""


def test_resolve_ai_config_treats_unfilled_placeholder_as_not_configured(monkeypatch):
    """.env.example ships ANTHROPIC_API_KEY=sk-ant-... as a placeholder --
    an unedited .env must not read as a real, configured key."""
    _clear_ai_env(monkeypatch)
    monkeypatch.setattr(providers.integration_credentials, "get_credentials", lambda user_id, name: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-...")

    cfg = providers.resolve_ai_config(1)
    assert cfg["api_key"] == ""


# --- OpenAIProvider message/tool translation (pure functions, no real API calls) ---

def test_to_openai_tool_translates_anthropic_schema():
    tool = {"name": "search_logs", "description": "Search logs", "input_schema": {"type": "object", "properties": {}}}
    result = providers.OpenAIProvider._to_openai_tool(tool)
    assert result == {
        "type": "function",
        "function": {"name": "search_logs", "description": "Search logs", "parameters": {"type": "object", "properties": {}}},
    }


def test_to_openai_messages_translates_assistant_tool_use_and_tool_result():
    messages = [
        {"role": "user", "content": "Investigate the incident."},
        {"role": "assistant", "content": [
            {"type": "text", "text": "Checking logs."},
            {"type": "tool_use", "id": "call_1", "name": "search_logs", "input": {"logql": "{app=\"x\"}"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call_1", "content": "no errors found"},
        ]},
    ]

    oai_messages = providers.OpenAIProvider._to_openai_messages("system prompt", messages)

    assert oai_messages[0] == {"role": "system", "content": "system prompt"}
    assert oai_messages[1] == {"role": "user", "content": "Investigate the incident."}
    assert oai_messages[2]["role"] == "assistant"
    assert oai_messages[2]["content"] == "Checking logs."
    assert oai_messages[2]["tool_calls"] == [
        {"id": "call_1", "type": "function", "function": {"name": "search_logs", "arguments": '{"logql": "{app=\\"x\\"}"}'}}
    ]
    assert oai_messages[3] == {"role": "tool", "tool_call_id": "call_1", "content": "no errors found"}


def test_openai_provider_step_normalizes_tool_call_response():
    class FakeToolCall:
        id = "call_2"
        function = type("F", (), {"name": "get_recent_changes", "arguments": "{}"})()

    class FakeMessage:
        content = None
        tool_calls = [FakeToolCall()]

    class FakeChoice:
        message = FakeMessage()

    class FakeUsage:
        prompt_tokens = 120
        completion_tokens = 40

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    class FakeCompletions:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return FakeResponse()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    provider = providers.OpenAIProvider.__new__(providers.OpenAIProvider)
    provider.client = FakeClient()
    provider.model = "gpt-4o-mini"

    result = provider.step(system="sys", tools=[], messages=[{"role": "user", "content": "hi"}])
    assert result["stop_reason"] == "tool_use"
    assert result["blocks"] == [{"type": "tool_use", "id": "call_2", "name": "get_recent_changes", "input": {}}]
    assert result["usage"] == {
        "input_tokens": 120, "output_tokens": 40,
        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
    }


def test_anthropic_provider_step_marks_system_and_last_tool_cacheable():
    """System prompt + TOOL_SCHEMAS are identical on every step of a run --
    marking the last block of each with cache_control lets steps 2+ read
    them from Anthropic's prompt cache instead of paying full price again."""
    class FakeUsage:
        input_tokens = 50
        output_tokens = 10
        cache_creation_input_tokens = 1200
        cache_read_input_tokens = 0

    class FakeResponse:
        content = []
        stop_reason = "end_turn"
        usage = FakeUsage()

    class FakeMessages:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return FakeResponse()

    class FakeClient:
        def __init__(self):
            self.messages = FakeMessages()

    provider = providers.AnthropicProvider.__new__(providers.AnthropicProvider)
    provider.client = FakeClient()
    provider.model = "claude-haiku-4-5"

    tools = [{"name": "tool_a", "input_schema": {}}, {"name": "tool_b", "input_schema": {}}]
    result = provider.step(system="you are an investigator", tools=tools, messages=[])

    sent_kwargs = provider.client.messages.kwargs
    assert sent_kwargs["system"] == [
        {"type": "text", "text": "you are an investigator", "cache_control": {"type": "ephemeral"}}
    ]
    assert sent_kwargs["tools"][0] == {"name": "tool_a", "input_schema": {}}
    assert sent_kwargs["tools"][1] == {"name": "tool_b", "input_schema": {}, "cache_control": {"type": "ephemeral"}}
    # original TOOL_SCHEMAS list/dicts must not be mutated in place
    assert tools[1] == {"name": "tool_b", "input_schema": {}}
    assert result["usage"] == {
        "input_tokens": 50, "output_tokens": 10,
        "cache_creation_input_tokens": 1200, "cache_read_input_tokens": 0,
    }
