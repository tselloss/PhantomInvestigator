"""The agent loop — the most important 60 lines of the project."""
import os

from langfuse import get_client

import providers
from schemas import Postmortem
from tools import TOOL_SCHEMAS, execute_tool

MAX_STEPS = int(os.environ.get("MAX_AGENT_STEPS", 10))
# Treated as USD for simplicity — no FX conversion, just a spend guardrail.
MAX_COST_PER_RUN = float(os.environ.get("MAX_COST_EUR_PER_RUN", 0.50))

# Per-1M-token USD pricing by model, used only to *estimate* cost_usd for
# display/budgeting — BYOK providers/models are billed to the operator's own
# account regardless. cache_write/cache_read apply to Anthropic's prompt
# caching (see providers.AnthropicProvider.step()); OpenAI caches
# automatically server-side with no separate token accounting exposed, so
# those stay 0 for its models. A model not listed here (e.g. a custom
# openai_compatible BYOK endpoint) gets no cost estimate rather than a
# silently wrong one borrowed from an unrelated model.
MODEL_PRICING_PER_1M = {
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "cache_write": 1.25, "cache_read": 0.10},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
    "claude-opus-4-8": {"input": 15.00, "output": 75.00, "cache_write": 18.75, "cache_read": 1.50},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cache_write": 0.0, "cache_read": 0.0},
    "gpt-4o": {"input": 2.50, "output": 10.00, "cache_write": 0.0, "cache_read": 0.0},
}


def _estimate_cost_usd(
    model: str, input_tokens: int, output_tokens: int, cache_write_tokens: int, cache_read_tokens: int
) -> float | None:
    pricing = MODEL_PRICING_PER_1M.get(model)
    if pricing is None:
        return None
    return round(
        input_tokens / 1_000_000 * pricing["input"]
        + output_tokens / 1_000_000 * pricing["output"]
        + cache_write_tokens / 1_000_000 * pricing["cache_write"]
        + cache_read_tokens / 1_000_000 * pricing["cache_read"],
        4,
    )

langfuse = get_client()

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "investigator.md")
SYSTEM_PROMPT = open(_PROMPT_PATH).read()

def run_agent(alert_text: str, owner_user_id: int, deployment_id: int | None = None) -> dict:
    """Non-streaming entry point: drains run_agent_stream and returns only
    the final result. Used by the Makefile, evals, and anything that just
    wants the answer (not progress updates)."""
    final = None
    for event in run_agent_stream(alert_text, owner_user_id, deployment_id=deployment_id):
        if event["type"] == "final":
            final = event["data"]
    return final

def run_agent_stream(alert_text: str, owner_user_id: int, deployment_id: int | None = None):
    """Generator version: yields progress events as the investigation runs,
    ending with exactly one {"type": "final", "data": <result dict>} event.
    Powers the UI's live view; run_agent() above just drains it."""
    with langfuse.start_as_current_observation(as_type="span", name="investigate") as trace:
        trace.update(input={"alert": alert_text})
        result = None
        for event in _run_agent_loop_stream(alert_text, owner_user_id, deployment_id=deployment_id):
            yield event
            if event["type"] == "final":
                result = event["data"]
        trace.update(output=result)
    langfuse.flush()

def _run_agent_loop_stream(alert_text: str, owner_user_id: int, deployment_id: int | None = None):
    provider = providers.get_provider(owner_user_id)
    messages = [{"role": "user", "content": f"Incident alert: {alert_text}. Investigate."}]
    input_tokens = 0
    output_tokens = 0
    cache_write_tokens = 0
    cache_read_tokens = 0
    usage = {
        "input_tokens": 0, "output_tokens": 0,
        "cache_write_tokens": 0, "cache_read_tokens": 0,
        "cost_usd": 0.0, "cost_estimated": True,
    }

    for step in range(1, MAX_STEPS + 1):
        # An unpriced (unknown) model can't be budget-capped in USD terms;
        # MAX_STEPS is the only guardrail left for it in that case.
        if usage["cost_usd"] is not None and usage["cost_usd"] >= MAX_COST_PER_RUN:
            yield {"type": "final", "data": {
                "steps": step - 1,
                "result": f"Stopped: budget cap (${MAX_COST_PER_RUN:.2f}) reached after {step - 1} steps.",
                "usage": usage,
                "partial": True,
            }}
            return

        yield {"type": "step_start", "step": step}

        with langfuse.start_as_current_observation(
            as_type="generation", name=f"step-{step}", model=provider.model
        ) as generation:
            result = provider.step(system=SYSTEM_PROMPT, tools=TOOL_SCHEMAS, messages=messages)
            blocks = result["blocks"]
            generation.update(
                input=messages,
                output=blocks,
                usage=result["usage"],
            )

        input_tokens += result["usage"]["input_tokens"]
        output_tokens += result["usage"]["output_tokens"]
        cache_write_tokens += result["usage"].get("cache_creation_input_tokens", 0)
        cache_read_tokens += result["usage"].get("cache_read_input_tokens", 0)
        cost_usd = _estimate_cost_usd(provider.model, input_tokens, output_tokens, cache_write_tokens, cache_read_tokens)
        usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_write_tokens": cache_write_tokens,
            "cache_read_tokens": cache_read_tokens,
            "cost_usd": cost_usd,
            "cost_estimated": cost_usd is not None,
        }

        if result["stop_reason"] != "tool_use":
            final_text = "".join(b["text"] for b in blocks if b["type"] == "text")
            yield {"type": "final", "data": {"steps": step, "result": final_text, "usage": usage}}
            return

        provider.append_assistant(messages, blocks)

        tool_results = []
        postmortem = None
        for block in blocks:
            if block["type"] != "tool_use":
                continue
            if block["name"] == "submit_postmortem":
                try:
                    postmortem = Postmortem(**block["input"])
                except Exception as e:
                    # Malformed structured output: let the model see the
                    # validation error and retry, rather than crashing the
                    # loop. Observed in practice under compound-fault
                    # incidents with a smaller model.
                    tool_results.append({
                        "tool_use_id": block["id"],
                        "content": f"ERROR: submit_postmortem input failed validation: {e}. Fix the input and call submit_postmortem again.",
                        "is_error": True,
                    })
                    continue
                tool_results.append({
                    "tool_use_id": block["id"],
                    "content": "Postmortem received.",
                })
                continue

            # Backstop, not a substitute for the prompt: if the model omits
            # deployment_id on a call (it's optional on these schemas for
            # backward compatibility, so nothing forces it), default-fill it
            # from what this investigation was actually started with, so a
            # per-client credential override still gets used even if the
            # model forgets to echo the id back.
            tool_args = dict(block["input"])
            if deployment_id is not None and tool_args.get("deployment_id") is None:
                tool_args["deployment_id"] = deployment_id

            yield {"type": "tool_call", "step": step, "name": block["name"], "input": tool_args}
            with langfuse.start_as_current_observation(
                name=f"tool:{block['name']}", as_type="tool", input=tool_args
            ) as tool_span:
                tool_result = execute_tool(block["name"], tool_args, owner_user_id)
                tool_span.update(output=tool_result)
            yield {"type": "tool_result", "step": step, "name": block["name"], "result": tool_result[:500]}

            tool_results.append({
                "tool_use_id": block["id"],
                "content": tool_result,
            })

        if postmortem is not None:
            yield {"type": "final", "data": {"steps": step, "postmortem": postmortem.model_dump(), "usage": usage}}
            return

        provider.append_tool_results(messages, tool_results)

    yield {"type": "final", "data": {
        "steps": MAX_STEPS,
        "result": "max steps reached without a final answer",
        "partial": True,
        "usage": usage,
    }}
