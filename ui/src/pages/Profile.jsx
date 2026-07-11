import { useEffect, useState } from "react";
import Icon from "../components/Icon";
import { useToast } from "../context/ToastContext";

export default function Profile() {
  const toast = useToast();
  const [profile, setProfile] = useState(null);
  const [editing, setEditing] = useState(false);
  const [limitInput, setLimitInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  async function load() {
    try {
      const res = await fetch("/api/settings/profile");
      if (!res.ok) throw new Error("load failed");
      setProfile(await res.json());
    } catch {
      toast.show("Couldn't load your profile — check your connection and reload.", { type: "err" });
    }
  }

  useEffect(() => {
    load();
  }, []);

  function startEdit() {
    setEditing(true);
    setSaveError(null);
    setLimitInput(profile?.monthly_limit_usd != null ? String(profile.monthly_limit_usd) : "");
  }

  async function saveLimit(monthlyLimitUsd) {
    setSaving(true);
    setSaveError(null);
    try {
      const res = await fetch("/api/settings/profile/limit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ monthly_limit_usd: monthlyLimitUsd }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        setSaveError(detail.detail || `HTTP ${res.status}`);
        return;
      }
      setEditing(false);
      await load();
    } finally {
      setSaving(false);
    }
  }

  function submitLimit() {
    const trimmed = limitInput.trim();
    if (trimmed === "") {
      saveLimit(null);
      return;
    }
    const parsed = Number(trimmed);
    if (Number.isNaN(parsed) || parsed < 0) {
      setSaveError("Enter a non-negative dollar amount, or leave blank for no cap.");
      return;
    }
    saveLimit(parsed);
  }

  if (!profile) return null;

  const { monthly_limit_usd: limit, spent_this_month_usd: spent } = profile;
  const pct = limit ? Math.min(100, (spent / limit) * 100) : 0;
  const barColor = limit == null ? "var(--accent)" : spent >= limit ? "var(--err)" : pct >= 80 ? "var(--warn)" : "var(--ok)";

  return (
    <>
      <section>
        <h2>Profile</h2>
        <p className="placeholder">Your account and how much of your own AI key this month's investigations have spent.</p>

        <div className="feed-row">
          <div className="row" style={{ gap: 8 }}>
            <span className="feed-source">{profile.username}</span>
            {profile.email && <span className="feed-meta">{profile.email}</span>}
            <span className="tag accent">{profile.sign_in_method === "google" ? "Google sign-in" : "Password sign-in"}</span>
          </div>
        </div>
      </section>

      <section>
        <h2>Monthly AI spend cap</h2>
        <p className="placeholder">
          Caps what this month's investigations can spend on your own AI key. Once reached, new investigations are
          blocked until the cap resets on the 1st, or you raise it here.
        </p>

        <div className="feed-row">
          <div className="row" style={{ gap: 8 }}>
            <span>
              ${spent.toFixed(2)} spent this month{limit != null ? ` of $${limit.toFixed(2)} cap` : ""}
            </span>
            {limit == null && <span className="badge ok">no cap set</span>}
            {limit != null && spent >= limit && <span className="badge err">cap reached</span>}
          </div>
          <div className="row" style={{ gap: 8 }}>
            <button onClick={() => (editing ? setEditing(false) : startEdit())}>{editing ? "Cancel" : "Edit"}</button>
            {limit != null && (
              <button className="danger" disabled={saving} onClick={() => saveLimit(null)}>
                Remove cap
              </button>
            )}
          </div>
        </div>

        {limit != null && (
          <div
            style={{
              height: 6, borderRadius: 3, background: "var(--accent-soft)", marginTop: 10, overflow: "hidden",
            }}
          >
            <div style={{ height: "100%", width: `${pct}%`, background: barColor, borderRadius: 3 }} />
          </div>
        )}

        {editing && (
          <div style={{ padding: "12px 0 0 0" }}>
            <div className="row" style={{ alignItems: "flex-end" }}>
              <div className="field">
                <label>Monthly cap (USD)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="No cap"
                  value={limitInput}
                  onChange={(e) => setLimitInput(e.target.value)}
                />
              </div>
              <button className="primary" disabled={saving} onClick={submitLimit}>
                <Icon name="check" size={14} />
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
            {saveError && <p style={{ color: "var(--err)", fontSize: 13, margin: "8px 0 0" }}>{saveError}</p>}
          </div>
        )}
      </section>
    </>
  );
}
