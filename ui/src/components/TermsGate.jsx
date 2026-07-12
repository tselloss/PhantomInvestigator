import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Button from "./Button";

/* Blocking first-use popup for accounts that reached the app without going
   through the Register form's Terms checkbox -- in practice, Google
   sign-ins, whose account creation is a redirect with no form step. Renders
   nothing once /auth/me reports tos_accepted: true. Not dismissible via
   backdrop click or Escape -- accepting (or signing out) are the only ways
   out, unlike CommandPalette's scrim. */
export default function TermsGate() {
  const { user, acceptTerms, logout } = useAuth();
  const [checked, setChecked] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  if (!user || user.tosAccepted) return null;

  async function handleAccept() {
    if (!checked) return;
    setSubmitting(true);
    await acceptTerms();
    setSubmitting(false);
  }

  return (
    <div className="palette-scrim" role="presentation">
      <div className="palette" role="dialog" aria-modal="true" aria-label="Accept Terms of Service">
        <div style={{ padding: "20px 22px 4px" }}>
          <h3 style={{ margin: "0 0 6px", fontSize: 16 }}>Before you continue</h3>
          <p className="placeholder" style={{ fontSize: 13, lineHeight: 1.55, margin: 0 }}>
            Phantom Investigator is free to use — no fees, no profit motive on our end. Please
            confirm you've read the{" "}
            <Link to="/terms" target="_blank" rel="noopener noreferrer">
              Terms of Service
            </Link>{" "}
            before continuing.
          </p>
        </div>
        <div style={{ padding: "14px 22px 20px", display: "flex", flexDirection: "column", gap: 14 }}>
          <label className="row" style={{ gap: 8, alignItems: "flex-start", fontSize: 12.5, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
              style={{ marginTop: 2 }}
            />
            <span className="placeholder">I have read and accept the Terms of Service</span>
          </label>
          <div className="row" style={{ gap: 10, justifyContent: "flex-end" }}>
            <Button onClick={logout}>Sign out instead</Button>
            <Button variant="primary" onClick={handleAccept} disabled={!checked} loading={submitting}>
              Accept and continue
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
