"""Covers loop.py's files_read tracking -- the guardrail fix_proposals.py
relies on to know which files the model actually read via get_file_contents
before trusting a proposed_fix_files entry (see agent/fix_proposals.py and
this feature's design notes in the git history)."""
import loop

MINIMAL_POSTMORTEM = {
    "title": "t", "root_cause": "r", "fault_category": "unknown", "confidence": 0.5,
    "timeline": [], "evidence": [], "suggested_fix": "f",
}


class FakeProvider:
    model = "test-model"

    def __init__(self, steps):
        self._steps = steps
        self.calls = 0

    def step(self, system, tools, messages):
        blocks, stop_reason = self._steps[self.calls]
        self.calls += 1
        return {"blocks": blocks, "usage": {"input_tokens": 1, "output_tokens": 1}, "stop_reason": stop_reason}

    def append_assistant(self, messages, blocks):
        pass

    def append_tool_results(self, messages, tool_results):
        pass


def _tool_use(id_, name, input_):
    return {"type": "tool_use", "id": id_, "name": name, "input": input_}


def _run(monkeypatch, steps, tool_result="file content"):
    provider = FakeProvider(steps)
    monkeypatch.setattr(loop.providers, "get_provider", lambda owner_user_id: provider)
    monkeypatch.setattr(loop, "execute_tool", lambda name, args, owner_user_id: tool_result)
    events = list(loop._run_agent_loop_stream("alert text", 1))
    return events[-1]["data"]


def test_files_read_includes_path_after_successful_get_file_contents(monkeypatch):
    steps = [
        ([_tool_use("1", "get_file_contents", {"repo": "o/r", "path": "a.py", "ref": "main"})], "tool_use"),
        ([_tool_use("2", "submit_postmortem", MINIMAL_POSTMORTEM)], "tool_use"),
    ]
    data = _run(monkeypatch, steps)
    assert data["files_read"] == ["a.py"]


def test_files_read_excludes_path_when_get_file_contents_errors(monkeypatch):
    steps = [
        ([_tool_use("1", "get_file_contents", {"repo": "o/r", "path": "a.py", "ref": "main"})], "tool_use"),
        ([_tool_use("2", "submit_postmortem", MINIMAL_POSTMORTEM)], "tool_use"),
    ]
    data = _run(monkeypatch, steps, tool_result="ERROR: not found")
    assert data["files_read"] == []


def test_files_read_ignores_other_tool_calls(monkeypatch):
    steps = [
        ([_tool_use("1", "search_runbooks", {"query": "x"})], "tool_use"),
        ([_tool_use("2", "submit_postmortem", MINIMAL_POSTMORTEM)], "tool_use"),
    ]
    data = _run(monkeypatch, steps)
    assert data["files_read"] == []


def test_files_read_present_on_plain_text_stop(monkeypatch):
    steps = [([{"type": "text", "text": "no tool use here"}], "end_turn")]
    data = _run(monkeypatch, steps)
    assert data["files_read"] == []
    assert "result" in data


def test_files_read_accumulates_across_multiple_calls(monkeypatch):
    steps = [
        ([_tool_use("1", "get_file_contents", {"repo": "o/r", "path": "a.py", "ref": "main"})], "tool_use"),
        ([_tool_use("2", "get_file_contents", {"repo": "o/r", "path": "b.py", "ref": "main"})], "tool_use"),
        ([_tool_use("3", "submit_postmortem", MINIMAL_POSTMORTEM)], "tool_use"),
    ]
    data = _run(monkeypatch, steps)
    assert data["files_read"] == ["a.py", "b.py"]
