import { useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import GoogleSignInButton from "../components/GoogleSignInButton";
import Icon from "../components/Icon";
import Button from "../components/Button";

export default function Register() {
  const { user, error, register } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [shakeNonce, setShakeNonce] = useState(0);

  if (user) {
    const dest = location.state?.from?.pathname || "/dashboard";
    return <Navigate to={dest} replace />;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    const ok = await register(username, password);
    setSubmitting(false);
    if (!ok) setShakeNonce((n) => n + 1);
  }

  return (
    <div className="auth-page" style={{ maxWidth: 380, margin: "0 auto" }}>
      <div style={{ textAlign: "center", marginBottom: 22 }}>
        <span className="brand-mark hero-mark hero-mark-float" style={{ width: 48, height: 48, margin: "0 auto 14px" }}>
          <Icon name="ghost" size={26} />
        </span>
        <h2 className="brand-shine" style={{ margin: "0 0 4px", fontSize: 19, fontWeight: 700 }}>
          Phantom Investigator
        </h2>
        <p className="placeholder" style={{ margin: 0, fontSize: 13 }}>
          Create your own account — your own workspace, your own AI key
        </p>
      </div>
      <section key={shakeNonce} className={shakeNonce > 0 ? "shake" : undefined}>
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
            <Button
              variant="primary"
              type="submit"
              loading={submitting}
              style={{ justifyContent: "center", marginTop: 4 }}
            >
              {submitting ? "Creating account…" : "Create account"}
            </Button>
            {error && <div className="alert err" style={{ margin: 0 }}>{error}</div>}
          </div>
        </form>
        <GoogleSignInButton />
      </section>
      <p className="placeholder" style={{ textAlign: "center", fontSize: 13, marginTop: 14 }}>
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </div>
  );
}
