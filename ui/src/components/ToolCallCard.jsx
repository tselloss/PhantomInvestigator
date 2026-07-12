import { useState } from "react";
import Icon from "./Icon";
import { truncate } from "../lib/format";

function formatDuration(ms) {
  if (ms == null) return null;
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function ToolCallCard({ name, input, output, pending, error, durationMs }) {
  const [open, setOpen] = useState(false);
  const statusClass = pending ? "pending" : error ? "err" : "ok";
  const preview = output ? truncate(output.replace(/\s+/g, " ").trim(), 70) : pending ? "running…" : "";

  function toggle() {
    setOpen((o) => !o);
  }

  return (
    <div className={"tool-card " + statusClass}>
      <div
        className="tool-card-summary"
        onClick={toggle}
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle();
          }
        }}
      >
        <span className={"tool-card-status " + statusClass}>
          {pending ? <span className="mini-spinner" /> : <Icon name={error ? "x" : "check"} size={13} />}
        </span>
        <span className="tool-card-name">{name}</span>
        <span className="tool-card-preview">{preview}</span>
        {durationMs != null && <span className="tool-card-duration">{formatDuration(durationMs)}</span>}
        <Icon
          name="chevron"
          size={13}
          className="tool-card-chevron"
          style={{ transform: open ? "rotate(90deg)" : "none" }}
        />
      </div>
      {open && (
        <div className="tool-card-body">
          <div className="tool-card-block">
            <label>Input</label>
            <pre>{JSON.stringify(input, null, 2)}</pre>
          </div>
          {output != null && (
            <div className="tool-card-block">
              <label>Output</label>
              <pre>{output}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
