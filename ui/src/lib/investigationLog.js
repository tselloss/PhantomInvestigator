// Turns one raw agent-loop event (the shape streamed over SSE, and the shape
// stored verbatim in an investigation's `trace`) into a timeline log entry.
// Shared so the live view (Investigate.jsx) and the static replay
// (InvestigationDetail.jsx) build identical entries from the same data.
export function eventToLogEntry(event) {
  switch (event.type) {
    case "step_start":
      return { kind: "step", step: event.step };
    case "tool_call":
      return { kind: "call", name: event.name, input: event.input };
    case "tool_result":
      return { kind: "out", text: event.result };
    default:
      return null;
  }
}
