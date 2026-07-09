"""One-shot vision pre-pass for reporter-attached screenshots. Deliberately
kept out of loop.py: this is a single non-agentic call to turn an image into
text, not a tool the investigator loop calls mid-run, so the 10-step/$0.50
budget and Langfuse tracing in loop.py stay untouched. Uses the same
operator-configured AI provider/key as the main loop (see providers.py)."""
import providers

EXTRACTION_PROMPT = """This screenshot was attached to a bug report by someone who may not have
described the problem in any detail elsewhere. Extract, as plain text:
- any error message or error text visible verbatim
- the general UI/page state (what screen, what the user appears to have been doing)
- any visible timestamps, URLs, request IDs, or stack traces
- anything else that looks obviously broken (layout, missing data, etc.)

Do not guess at the root cause -- only describe what is visibly present in the image.
If the image doesn't look like an error or bug at all, say so plainly."""


def describe_screenshot(image_bytes: bytes, content_type: str, user_id: int) -> str:
    """Raises on failure (SDK error, timeout) rather than swallowing --
    callers decide the fallback, and this stays directly mockable in tests
    the same way loop.run_agent is mocked at its own boundary."""
    return providers.get_provider(user_id).vision(image_bytes, content_type, EXTRACTION_PROMPT)
