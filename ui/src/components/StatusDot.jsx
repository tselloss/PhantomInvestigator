export default function StatusDot({ status = "ok", live = false, label, size = 6, className = "" }) {
  return (
    <span className={"status-dot-wrap " + className}>
      <span
        className={"status-dot status-dot-" + status + (live ? " live" : "")}
        style={{ width: size, height: size }}
        aria-hidden="true"
      />
      {label && <span className="status-dot-label">{label}</span>}
    </span>
  );
}
