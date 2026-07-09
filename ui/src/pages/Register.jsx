import { useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const { user, error, register } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (user) {
    const dest = location.state?.from?.pathname || "/dashboard";
    return <Navigate to={dest} replace />;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    await register(username, password);
    setSubmitting(false);
  }

  return (
    <main style={{ maxWidth: 380, margin: "12vh auto 0" }}>
      <div style={{ textAlign: "center", marginBottom: 22 }}>
        <span className="brand-mark" style={{ width: 48, height: 48, fontSize: 24, margin: "0 auto 14px" }}>
          👻
        </span>
        <h2 style={{ margin: "0 0 4px", fontSize: 19, fontWeight: 700 }}>Phantom Investigator</h2>
        <p className="placeholder" style={{ margin: 0, fontSize: 13 }}>
          Create your own account — your own workspace, your own AI key
        </p>
      </div>
      <section>
        <form onSubmit={handleSubmit}>
          <div className="row" style={{ flexDirection: "column", alignItems: "stretch", gap: 14 }}>
            <div className="field">
              <label htmlFor="register-username">Username</label>
              <input
                id="register-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
              />
            </div>
            <div className="field">
              <label htmlFor="register-password">Password</label>
              <input
                id="register-password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <button className="primary" type="submit" disabled={submitting} style={{ justifyContent: "center", marginTop: 4 }}>
              {submitting ? "Creating account…" : "Create account"}
            </button>
            {error && <p style={{ color: "var(--err)", fontSize: 13, margin: 0 }}>{error}</p>}
          </div>
        </form>
      </section>
      <p className="placeholder" style={{ textAlign: "center", fontSize: 13, marginTop: 14 }}>
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </main>
  );
}
