import Icon from "./Icon";
import ToolCallCard from "./ToolCallCard";

function groupSteps(log) {
  const steps = [];
  let current = null;
  for (const entry of log) {
    if (entry.kind === "step") {
      current = { step: entry.step, at: entry.at, calls: [] };
      steps.push(current);
    } else if (entry.kind === "call") {
      current?.calls.push({ name: entry.name, input: entry.input, at: entry.at, result: null, resultAt: null, error: false });
    } else if (entry.kind === "out" && current) {
      const call = [...current.calls].reverse().find((c) => c.result === null);
      if (call) {
        call.result = entry.text;
        call.resultAt = entry.at;
        call.error = /^ERROR:/i.test(entry.text || "");
      }
    }
  }
  return steps;
}

export default function InvestigationTimeline({ log, running }) {
  const steps = groupSteps(log);

  return (
    <div className="timeline">
      {steps.map((s, i) => {
        const isLast = i === steps.length - 1;
        const active = isLast && running;
        const nextAt = steps[i + 1]?.at;
        const stepDurationMs = !active && nextAt ? nextAt - s.at : null;

        return (
          <div key={s.step} className={"timeline-step " + (active ? "active" : "done")}>
            <div className="timeline-step-dot">{active ? null : <Icon name="check" size={11} />}</div>
            <div className="timeline-step-head">
              <span>Step {s.step}</span>
              {stepDurationMs != null && <span className="step-duration">{(stepDurationMs / 1000).toFixed(1)}s</span>}
            </div>
            <div className="timeline-step-body">
              {s.calls.length === 0 && active && (
                <div className="timeline-thinking">
                  <span className="mini-spinner" />
                  thinking…
                </div>
              )}
              {s.calls.map((c, ci) => {
                const unresolved = c.result == null;
                const pending = unresolved && running;
                const interrupted = unresolved && !running;
                return (
                  <ToolCallCard
                    key={ci}
                    name={c.name}
                    input={c.input}
                    output={interrupted ? "(no result — investigation stopped before this call finished)" : c.result}
                    pending={pending}
                    error={c.error || interrupted}
                    durationMs={c.resultAt ? c.resultAt - c.at : null}
                  />
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
