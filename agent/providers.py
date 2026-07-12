"""AI provider abstraction (bring-your-own-key). Resolves which model/key/
base_url powers the investigation loop from the operator's own Settings ->
Integrations "AI provider" entry, falling back to .env, and normalizes
Anthropic vs. OpenAI-compatible tool-calling into one shape loop.py and
vision.py can drive without caring which provider is configured.

The neutral message/block format used by both providers' public methods is
Anthropic's own wire format -- {"type": "text", "text": ...} / {"type":
"tool_use", "id", "name", "input"} content blocks, and a `messages` list of
{"role", "content"} -- since that's what already worked before BYOK existed.
AnthropicProvider passes it straight through; OpenAIProvider translates it to
and from OpenAI's wire format on every call.
"""
import json
import os

import anthropic
import openai

import integration_credentials

DEFAULT_MODEL_BY_PROVIDER = {
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-4o-mini",
    "openai_compatible": "gpt-4o-mini",
}


def resolve_ai_config(user_id: int) -> dict:
    """{provider, api_key, model, base_url}. DB override (per-user -- this
    key funds this user's own usage, not a specific investigated client, so
    there's no per-deployment scoping like the other integrations) merged
    over AI_* env vars. When provider is "anthropic" and AI_API_KEY/AI_MODEL
    are unset, falls back to the legacy ANTHROPIC_API_KEY/ANTHROPIC_MODEL so
    existing .env files keep working unmodified."""
    override = integration_credentials.get_credentials(user_id, "ai") or {}

    provider = override.get("provider") or os.environ.get("AI_PROVIDER") or "anthropic"

    api_key = override.get("api_key") or os.environ.get("AI_API_KEY") or ""
    if not api_key and provider == "anthropic":
        env_key = os.environ.get("ANTHROPIC_API_KEY", "")
        # .env.example ships ANTHROPIC_API_KEY=sk-ant-... as a placeholder,
        # not a real value -- an unedited .env would otherwise read as
        # "configured" (see scripts/setup.sh's own is_blank() for the same
        # "..." convention).
        api_key = env_key if not env_key.endswith("...") else ""

    model = override.get("model") or os.environ.get("AI_MODEL") or ""
    if not model and provider == "anthropic":
        model = os.environ.get("ANTHROPIC_MODEL", "")
    if not model:
        model = DEFAULT_MODEL_BY_PROVIDER.get(provider, DEFAULT_MODEL_BY_PROVIDER["anthropic"])

    base_url = override.get("base_url") or os.environ.get("AI_BASE_URL") or ""

    return {"provider": provider, "api_key": api_key, "model": model, "base_url": base_url}


def get_provider(user_id: int):
    """Built fresh from resolve_ai_config() on every call (no cached
    singleton) so a key rotated in Settings takes effect immediately,
    matching every other tool's "no restart needed" behavior."""
    cfg = resolve_ai_config(user_id)
    if cfg["provider"] == "anthropic":
        return AnthropicProvider(cfg["api_key"], cfg["model"])
    return OpenAIProvider(cfg["api_key"], cfg["model"], base_url=cfg["base_url"] or None)


class AnthropicProvider:
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key or None)
        self.model = model

    def step(self, system: str, tools: list[dict], messages: list[dict]) -> dict:
        # Both the system prompt and TOOL_SCHEMAS are identical on every step
        # of a run (and across runs, until the prompt/tools change) -- marking
        # the last block of each with cache_control caches everything up to
        # and including it, so steps 2+ of a multi-step investigation read
        # this from cache instead of paying full input price for it again.
        cached_system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        cached_tools = tools
        if tools:
            cached_tools = [*tools[:-1], {**tools[-1], "cache_control": {"type": "ephemeral"}}]
        resp = self.client.messages.create(
            model=self.model, max_tokens=2000, system=cached_system, tools=cached_tools, messages=messages,
        )
        return {
            "blocks": [b.model_dump() for b in resp.content],
            "stop_reason": resp.stop_reason,
            "usage": {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "cache_creation_input_tokens": resp.usage.cache_creation_input_tokens or 0,
                "cache_read_input_tokens": resp.usage.cache_read_input_tokens or 0,
            },
        }

    def append_assistant(self, messages: list[dict], blocks: list[dict]) -> None:
        messages.append({"role": "assistant", "content": blocks})

    def append_tool_results(self, messages: list[dict], tool_results: list[dict]) -> None:
        messages.append({
            "role": "user",
            "content": [{"type": "tool_result", **tr} for tr in tool_results],
        })

    def vision(self, image_bytes: bytes, content_type: str, prompt: str) -> str:
        import base64
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            timeout=20.0,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": content_type,
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return "".join(block.text for block in resp.content if block.type == "text").strip()

    def test(self) -> None:
        self.client.models.list(limit=1)


class OpenAIProvider:
    """Used for both provider="openai" and provider="openai_compatible" --
    the only difference is base_url."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self.client = openai.OpenAI(api_key=api_key or None, base_url=base_url)
        self.model = model

    @staticmethod
    def _to_openai_tool(tool: dict) -> dict:
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool["input_schema"],
            },
        }

    @staticmethod
    def _to_openai_messages(system: str, messages: list[dict]) -> list[dict]:
        oai_messages = [{"role": "system", "content": system}]
        for msg in messages:
            content = msg["content"]
            if isinstance(content, str):
                oai_messages.append({"role": msg["role"], "content": content})
                continue

            if msg["role"] == "assistant":
                text = "".join(b["text"] for b in content if b["type"] == "text") or None
                tool_calls = [
                    {
                        "id": b["id"],
                        "type": "function",
                        "function": {"name": b["name"], "arguments": json.dumps(b["input"])},
                    }
                    for b in content if b["type"] == "tool_use"
                ]
                entry = {"role": "assistant", "content": text}
                if tool_calls:
                    entry["tool_calls"] = tool_calls
                oai_messages.append(entry)
            else:
                for block in content:
                    if block["type"] == "tool_result":
                        oai_messages.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block["content"],
                        })
        return oai_messages

    def step(self, system: str, tools: list[dict], messages: list[dict]) -> dict:
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=2000,
            tools=[self._to_openai_tool(t) for t in tools],
            messages=self._to_openai_messages(system, messages),
        )
        choice = resp.choices[0]
        blocks = []
        if choice.message.content:
            blocks.append({"type": "text", "text": choice.message.content})
        for tc in choice.message.tool_calls or []:
            blocks.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": json.loads(tc.function.arguments or "{}"),
            })
        stop_reason = "tool_use" if choice.message.tool_calls else "end_turn"
        usage = resp.usage
        return {
            "blocks": blocks,
            "stop_reason": stop_reason,
            "usage": {
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0,
                # OpenAI caches automatically server-side with no separate
                # accounting exposed here -- these stay 0 so loop.py's cost
                # math has one shape to deal with regardless of provider.
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        }

    def append_assistant(self, messages: list[dict], blocks: list[dict]) -> None:
        messages.append({"role": "assistant", "content": blocks})

    def append_tool_results(self, messages: list[dict], tool_results: list[dict]) -> None:
        messages.append({
            "role": "user",
            "content": [{"type": "tool_result", **tr} for tr in tool_results],
        })

    def vision(self, image_bytes: bytes, content_type: str, prompt: str) -> str:
        import base64
        data_uri = f"data:{content_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=500,
            timeout=20.0,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return (resp.choices[0].message.content or "").strip()

    def test(self) -> None:
        self.client.models.list()
