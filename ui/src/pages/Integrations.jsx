import { useEffect, useState } from "react";
import Button from "../components/Button";
import Card from "../components/Card";
import StatusDot from "../components/StatusDot";
import RevealInput from "../components/RevealInput";
import Skeleton from "../components/Skeleton";
import { integrationLabel, integrationRole } from "../lib/integrations";
import { useToast } from "../context/ToastContext";

export default function Integrations() {
  const toast = useToast();
  const [integrations, setIntegrations] = useState(null);
  const [fieldSchema, setFieldSchema] = useState({});
  const [testing, setTesting] = useState(null);
  const [results, setResults] = useState({});
  const [editing, setEditing] = useState(null);
  const [formValues, setFormValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [confirmClear, setConfirmClear] = useState(null);

  const [aiStatus, setAiStatus] = useState(null);
  const [aiFields, setAiFields] = useState([]);
  const [aiTesting, setAiTesting] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [aiEditing, setAiEditing] = useState(false);
  const [aiFormValues, setAiFormValues] = useState({});
  const [aiSaving, setAiSaving] = useState(false);
  const [aiSaveError, setAiSaveError] = useState(null);
  const [confirmClearAi, setConfirmClearAi] = useState(false);

  async function load() {
    try {
      const [intRes, fieldsRes, aiRes, aiFieldsRes] = await Promise.all([
        fetch("/api/settings/integrations"),
        fetch("/api/settings/integrations/fields"),
        fetch("/api/settings/ai"),
        fetch("/api/settings/ai/fields"),
      ]);
      if (![intRes, fieldsRes, aiRes, aiFieldsRes].every((r) => r.ok)) throw new Error("load failed");
      setIntegrations(await intRes.json());
      setFieldSchema(await fieldsRes.json());
      setAiStatus(await aiRes.json());
      setAiFields(await aiFieldsRes.json());
    } catch {
      toast.show("Couldn't load integration settings — check your connection and reload.", { type: "err" });
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function testAi() {
    setAiTesting(true);
    try {
      const res = await fetch("/api/settings/ai/test", { method: "POST" });
      const data = await res.json().catch(() => ({ ok: false, detail: `HTTP ${res.status}` }));
      setAiResult(data);
      toast.show(data.detail || (data.ok ? "Connection OK." : "Connection failed."), { type: data.ok ? "ok" : "err" });
    } catch {
      setAiResult({ ok: false, detail: "Connection test failed — check your connection." });
      toast.show("Connection test failed — check your connection.", { type: "err" });
    } finally {
      setAiTesting(false);
    }
  }

  async function clearAi() {
    setConfirmClearAi(false);
    try {
      const res = await fetch("/api/settings/ai", { method: "DELETE" });
      if (!res.ok) {
        toast.show(`Couldn't clear AI provider override (HTTP ${res.status})`, { type: "err" });
        return;
      }
      await load();
      toast.show("AI provider override cleared.", { type: "ok" });
    } catch {
      toast.show("Couldn't clear AI provider override — check your connection.", { type: "err" });
    }
  }

  async function test(name) {
    setTesting(name);
    try {
      const res = await fetch(`/api/settings/integrations/${name}/test`, { method: "POST" });
      const data = await res.json().catch(() => ({ ok: false, detail: `HTTP ${res.status}` }));
      setResults((r) => ({ ...r, [name]: data }));
      toast.show(data.detail || (data.ok ? "Connection OK." : "Connection failed."), { type: data.ok ? "ok" : "err" });
    } catch {
      const data = { ok: false, detail: "Connection test failed — check your connection." };
      setResults((r) => ({ ...r, [name]: data }));
      toast.show(data.detail, { type: "err" });
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
      toast.show(`${integrationLabel(name)} saved.`, { type: "ok" });
    } catch {
      toast.show("Couldn't save — check your connection.", { type: "err" });
    } finally {
      setSaving(false);
    }
  }

  async function clearOverride(name) {
    setConfirmClear(null);
    try {
      const res = await fetch(`/api/settings/integrations/${name}`, { method: "DELETE" });
      if (!res.ok) {
        toast.show(`Couldn't clear override (HTTP ${res.status})`, { type: "err" });
        return;
      }
      await load();
      toast.show(`${integrationLabel(name)} override cleared.`, { type: "ok" });
    } catch {
      toast.show("Couldn't clear override — check your connection.", { type: "err" });
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
      toast.show("AI provider saved.", { type: "ok" });
    } catch {
      toast.show("Couldn't save — check your connection.", { type: "err" });
    } finally {
      setAiSaving(false);
    }
  }

  return (
    <>
      <section>
        <h2>AI provider (required)</h2>
        <p className="placeholder">
          The key that powers investigations — bring your own Claude, OpenAI, or compatible key. Billed to your
          account, never stored in plaintext, never shown here once saved.
        </p>

        {aiStatus === null ? (
          <Skeleton height={54} radius={12} />
        ) : (
        <Card status={aiStatus?.configured ? "ok" : "warn"}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div className="row" style={{ gap: 10 }}>
              <StatusDot status={aiStatus?.configured ? "ok" : "muted"} />
              <span style={{ fontWeight: 600 }}>{aiStatus?.provider || "ai"}</span>
              {aiStatus?.override && <span className="tag accent">stored override</span>}
              {aiResult && (
                <span style={{ color: aiResult.ok ? "var(--ok)" : "var(--err)", fontSize: 13 }}>{aiResult.detail}</span>
              )}
            </div>
            <div className="row" style={{ gap: 8 }}>
              <Button onClick={() => (aiEditing ? setAiEditing(false) : startAiEdit())}>
                {aiEditing ? "Cancel" : aiStatus?.override ? "Edit" : "Set up"}
              </Button>
              {aiStatus?.override && (
                confirmClearAi ? (
                  <>
                    <span className="placeholder" style={{ fontSize: 13 }}>Clear this override?</span>
                    <Button variant="danger" onClick={clearAi}>Confirm</Button>
                    <Button variant="ghost" onClick={() => setConfirmClearAi(false)}>Cancel</Button>
                  </>
                ) : (
                  <Button variant="danger" onClick={() => setConfirmClearAi(true)}>
                    Clear override
                  </Button>
                )
              )}
              <Button disabled={!aiStatus?.configured} loading={aiTesting} onClick={testAi}>
                {aiTesting ? "Testing…" : "Test connection"}
              </Button>
            </div>
          </div>

          {aiEditing && (
            <div style={{ padding: "14px 0 0 0" }}>
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
                      {f.secret ? (
                        <RevealInput
                          placeholder={aiStatus?.override ? "Leave blank to keep current value" : "Optional"}
                          value={aiFormValues[f.key] || ""}
                          onChange={(e) => setAiFormValues((v) => ({ ...v, [f.key]: e.target.value }))}
                        />
                      ) : (
                        <input
                          type="text"
                          placeholder={aiStatus?.override ? "Leave blank to keep current value" : "Optional"}
                          value={aiFormValues[f.key] || ""}
                          onChange={(e) => setAiFormValues((v) => ({ ...v, [f.key]: e.target.value }))}
                        />
                      )}
                    </div>
                  )
                )}
                <Button
                  variant="primary"
                  icon="check"
                  loading={aiSaving}
                  disabled={!Object.values(aiFormValues).some((v) => v.trim())}
                  onClick={saveAi}
                >
                  {aiSaving ? "Saving…" : "Save"}
                </Button>
              </div>
              {aiSaveError && <p style={{ color: "var(--err)", fontSize: 13, margin: "8px 0 0" }}>{aiSaveError}</p>}
            </div>
          )}
        </Card>
        )}
      </section>

      <section>
        <h2>Integrations</h2>
        <p className="placeholder">
          Set credentials here, or via .env — either way this page never displays saved values, only presence and
          live connection status.
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {integrations === null && (
            <>
              <Skeleton height={54} radius={12} />
              <Skeleton height={54} radius={12} />
              <Skeleton height={54} radius={12} />
            </>
          )}
          {integrations?.map((i) => (
            <Card key={i.name} status={i.configured ? "ok" : "warn"}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <div className="row" style={{ gap: 10 }}>
                  <StatusDot status={i.configured ? "ok" : "muted"} />
                  <span style={{ fontWeight: 600 }}>{integrationLabel(i.name)}</span>
                  <span className="feed-meta">{integrationRole(i.name)}</span>
                  {i.override && <span className="tag accent">stored override</span>}
                  {results[i.name] && (
                    <span style={{ color: results[i.name].ok ? "var(--ok)" : "var(--err)", fontSize: 13 }}>
                      {results[i.name].detail}
                    </span>
                  )}
                </div>
                <div className="row" style={{ gap: 8 }}>
                  {i.editable && (
                    <Button onClick={() => (editing === i.name ? cancelEdit() : startEdit(i.name))}>
                      {editing === i.name ? "Cancel" : i.override ? "Edit" : "Set up"}
                    </Button>
                  )}
                  {i.override && (
                    confirmClear === i.name ? (
                      <>
                        <span className="placeholder" style={{ fontSize: 13 }}>Clear this override?</span>
                        <Button variant="danger" onClick={() => clearOverride(i.name)}>Confirm</Button>
                        <Button variant="ghost" onClick={() => setConfirmClear(null)}>Cancel</Button>
                      </>
                    ) : (
                      <Button variant="danger" onClick={() => setConfirmClear(i.name)}>
                        Clear override
                      </Button>
                    )
                  )}
                  <Button disabled={!i.configured} loading={testing === i.name} onClick={() => test(i.name)}>
                    {testing === i.name ? "Testing…" : "Test connection"}
                  </Button>
                </div>
              </div>

              {editing === i.name && (
                <div style={{ padding: "14px 0 0 0" }}>
                  <div className="row" style={{ alignItems: "flex-end" }}>
                    {(fieldSchema[i.name] || []).map((f) => (
                      <div className="field" key={f.key}>
                        <label>{f.label}</label>
                        {f.secret ? (
                          <RevealInput
                            placeholder={i.override ? "Leave blank to keep current value" : "Optional"}
                            value={formValues[f.key] || ""}
                            onChange={(e) => setFormValues((v) => ({ ...v, [f.key]: e.target.value }))}
                          />
                        ) : (
                          <input
                            type="text"
                            placeholder={i.override ? "Leave blank to keep current value" : "Optional"}
                            value={formValues[f.key] || ""}
                            onChange={(e) => setFormValues((v) => ({ ...v, [f.key]: e.target.value }))}
                          />
                        )}
                      </div>
                    ))}
                    <Button
                      variant="primary"
                      icon="check"
                      loading={saving}
                      disabled={!Object.values(formValues).some((v) => v.trim())}
                      onClick={() => save(i.name)}
                    >
                      {saving ? "Saving…" : "Save"}
                    </Button>
                  </div>
                  {saveError && <p style={{ color: "var(--err)", fontSize: 13, margin: "8px 0 0" }}>{saveError}</p>}
                </div>
              )}
            </Card>
          ))}
        </div>
      </section>
    </>
  );
}
