import { useEffect, useState } from "react";
import Icon from "../components/Icon";

export default function Integrations() {
  const [integrations, setIntegrations] = useState([]);
  const [fieldSchema, setFieldSchema] = useState({});
  const [testing, setTesting] = useState(null);
  const [results, setResults] = useState({});
  const [editing, setEditing] = useState(null);
  const [formValues, setFormValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const [aiStatus, setAiStatus] = useState(null);
  const [aiFields, setAiFields] = useState([]);
  const [aiTesting, setAiTesting] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [aiEditing, setAiEditing] = useState(false);
  const [aiFormValues, setAiFormValues] = useState({});
  const [aiSaving, setAiSaving] = useState(false);
  const [aiSaveError, setAiSaveError] = useState(null);

  async function load() {
    const [intRes, fieldsRes, aiRes, aiFieldsRes] = await Promise.all([
      fetch("/api/settings/integrations"),
      fetch("/api/settings/integrations/fields"),
      fetch("/api/settings/ai"),
      fetch("/api/settings/ai/fields"),
    ]);
    setIntegrations(await intRes.json());
    setFieldSchema(await fieldsRes.json());
    setAiStatus(await aiRes.json());
    setAiFields(await aiFieldsRes.json());
  }

  useEffect(() => {
    load();
  }, []);

  async function testAi() {
    setAiTesting(true);
    try {
      const res = await fetch("/api/settings/ai/test", { method: "POST" });
      setAiResult(await res.json());
    } finally {
      setAiTesting(false);
    }
  }

  function startAiEdit() {
    setAiEditing(true);
    setAiSaveError(null);
    const blank = {};
    aiFields.forEach((f) => (blank[f.key] = ""));
    setAiFormValues(blank);
  }

  async function saveAi() {
    setAiSaving(true);
    setAiSaveError(null);
    try {
      const res = await fetch("/api/settings/ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(aiFormValues),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        setAiSaveError(detail.detail || `HTTP ${res.status}`);
        return;
      }
      setAiEditing(false);
      await load();
    } finally {
      setAiSaving(false);
    }
  }

  async function clearAi() {
    await fetch("/api/settings/ai", { method: "DELETE" });
    await load();
  }

  async function test(name) {
    setTesting(name);
    try {
      const res = await fetch(`/api/settings/integrations/${name}/test`, { method: "POST" });
      const data = await res.json();
      setResults((r) => ({ ...r, [name]: data }));
    } finally {
      setTesting(null);
    }
  }

  function startEdit(name) {
    setEditing(name);
    setSaveError(null);
    const blank = {};
    (fieldSchema[name] || []).forEach((f) => (blank[f.key] = ""));
    setFormValues(blank);
  }

  function cancelEdit() {
    setEditing(null);
    setSaveError(null);
  }

  async function save(name) {
    setSaving(true);
    setSaveError(null);
    try {
      const res = await fetch(`/api/settings/integrations/${name}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formValues),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        setSaveError(detail.detail || `HTTP ${res.status}`);
        return;
      }
      setEditing(null);
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function clearOverride(name) {
    await fetch(`/api/settings/integrations/${name}`, { method: "DELETE" });
    await load();
  }

  return (
    <>
      <section>
        <h2>AI provider (required)</h2>
        <p className="placeholder">
          The key that powers investigations — bring your own Claude, OpenAI, or compatible key. Billed to your
          account, never stored in plaintext, never shown here once saved.
        </p>

        <div className="feed-row">
          <div className="row" style={{ gap: 8 }}>
            <span className="feed-source">{aiStatus?.provider || "ai"}</span>
            <span className={"badge " + (aiStatus?.configured ? "ok" : "warn")}>
              {aiStatus?.configured ? "configured" : "not configured"}
            </span>
            {aiStatus?.override && <span className="tag accent">stored override</span>}
            {aiResult && (
              <span style={{ color: aiResult.ok ? "var(--ok)" : "var(--err)" }}>{aiResult.detail}</span>
            )}
          </div>
          <div className="row" style={{ gap: 8 }}>
            <button onClick={() => (aiEditing ? setAiEditing(false) : startAiEdit())}>
              {aiEditing ? "Cancel" : aiStatus?.override ? "Edit" : "Set up"}
            </button>
            {aiStatus?.override && (
              <button className="danger" onClick={clearAi}>
                Clear override
              </button>
            )}
            <button disabled={!aiStatus?.configured || aiTesting} onClick={testAi}>
              {aiTesting ? "Testing…" : "Test connection"}
            </button>
          </div>
        </div>

        {aiEditing && (
          <div style={{ padding: "4px 0 0 0" }}>
            <div className="row" style={{ alignItems: "flex-end" }}>
              {aiFields.map((f) =>
                f.options ? (
                  <div className="field" key={f.key}>
                    <label>{f.label}</label>
                    <select
                      value={aiFormValues[f.key] || ""}
                      onChange={(e) => setAiFormValues((v) => ({ ...v, [f.key]: e.target.value }))}
                    >
                      <option value="">{aiStatus?.override ? "Leave unchanged" : "anthropic (default)"}</option>
                      {f.options.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <div className="field" key={f.key}>
                    <label>{f.label}</label>
                    <input
                      type={f.secret ? "password" : "text"}
                      placeholder={aiStatus?.override ? "Leave blank to keep current value" : "Optional"}
                      value={aiFormValues[f.key] || ""}
                      onChange={(e) => setAiFormValues((v) => ({ ...v, [f.key]: e.target.value }))}
                    />
                  </div>
                )
              )}
              <button
                className="primary"
                disabled={aiSaving || !Object.values(aiFormValues).some((v) => v.trim())}
                onClick={saveAi}
              >
                <Icon name="check" size={14} />
                {aiSaving ? "Saving…" : "Save"}
              </button>
            </div>
            {aiSaveError && <p style={{ color: "var(--err)", fontSize: 13, margin: "8px 0 0" }}>{aiSaveError}</p>}
          </div>
        )}
      </section>

      <section>
        <h2>Integrations</h2>
        <p className="placeholder">
          Set credentials here, or via .env — either way this page never displays saved values, only presence and
          live connection status.
        </p>

        {integrations.map((i) => (
        <div key={i.name}>
          <div className="feed-row">
            <div className="row" style={{ gap: 8 }}>
              <span className="feed-source">{i.name}</span>
              <span className={"badge " + (i.configured ? "ok" : "warn")}>
                {i.configured ? "configured" : "not configured"}
              </span>
              {i.override && <span className="tag accent">stored override</span>}
              {results[i.name] && (
                <span style={{ color: results[i.name].ok ? "var(--ok)" : "var(--err)" }}>
                  {results[i.name].detail}
                </span>
              )}
            </div>
            <div className="row" style={{ gap: 8 }}>
              {i.editable && (
                <button onClick={() => (editing === i.name ? cancelEdit() : startEdit(i.name))}>
                  {editing === i.name ? "Cancel" : i.override ? "Edit" : "Set up"}
                </button>
              )}
              {i.override && (
                <button className="danger" onClick={() => clearOverride(i.name)}>
                  Clear override
                </button>
              )}
              <button disabled={!i.configured || testing === i.name} onClick={() => test(i.name)}>
                {testing === i.name ? "Testing…" : "Test connection"}
              </button>
            </div>
          </div>

          {editing === i.name && (
            <div style={{ padding: "4px 0 16px 0" }}>
              <div className="row" style={{ alignItems: "flex-end" }}>
                {(fieldSchema[i.name] || []).map((f) => (
                  <div className="field" key={f.key}>
                    <label>{f.label}</label>
                    <input
                      type={f.secret ? "password" : "text"}
                      placeholder={i.override ? "Leave blank to keep current value" : "Optional"}
                      value={formValues[f.key] || ""}
                      onChange={(e) => setFormValues((v) => ({ ...v, [f.key]: e.target.value }))}
                    />
                  </div>
                ))}
                <button
                  className="primary"
                  disabled={saving || !Object.values(formValues).some((v) => v.trim())}
                  onClick={() => save(i.name)}
                >
                  <Icon name="check" size={14} />
                  {saving ? "Saving…" : "Save"}
                </button>
              </div>
              {saveError && <p style={{ color: "var(--err)", fontSize: 13, margin: "8px 0 0" }}>{saveError}</p>}
            </div>
          )}
        </div>
        ))}
      </section>
    </>
  );
}
