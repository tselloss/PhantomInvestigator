function lineClass(line) {
  if (line.startsWith("+++") || line.startsWith("---")) return "diff-line-meta";
  if (line.startsWith("@@")) return "diff-line-hunk";
  if (line.startsWith("+")) return "diff-line-add";
  if (line.startsWith("-")) return "diff-line-del";
  return "diff-line-ctx";
}

// Renders a precomputed unified diff (produced server-side by
// fix_proposals.py via Python's difflib) as plain +/-/context colored
// lines -- no diff-rendering library exists in this app, and none is
// needed since the diff text itself is already computed by the backend.
export default function DiffView({ path, diff }) {
  const lines = (diff || "").split("\n");
  return (
    <div className="diff-view">
      {path && <div className="diff-view-path">{path}</div>}
      <pre className="diff-view-body">
        {lines.map((line, i) => (
          <div key={i} className={lineClass(line)}>
            {line || " "}
          </div>
        ))}
      </pre>
    </div>
  );
}
