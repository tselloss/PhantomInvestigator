import { useState } from "react";
import { Link, Navigate, useLocation, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import GoogleSignInButton from "../components/GoogleSignInButton";

export default function Login() {
  const { user, error, login } = useAuth();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const googleError = searchParams.get("error") === "google_failed" ? "Google sign-in failed — try again." : null;

  if (user) {
    const dest = location.state?.from?.pathname || "/dashboard";
    return <Navigate to={dest} replace />;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    await login(username, password);
    setSubmitting(false);
  }

  return (
    <div className="auth-page" style={{ maxWidth: 380, margin: "0 auto" }}>
      <div style={{ textAlign: "center", marginBottom: 22 }}>
        <span className="brand-mark hero-mark" style={{ width: 48, height: 48, fontSize: 24, margin: "0 auto 14px" }}>
          👻
        </span>
        <h2 className="brand-shine" style={{ margin: "0 0 4px", fontSize: 19, fontWeight: 700 }}>
          Phantom Investigator
        </h2>
        <p className="placeholder" style={{ margin: 0, fontSize: 13 }}>
          Sign in to the operator console
        </p>
      </div>
      <section>
        <form onSubmit={handleSubmit}>
          <div className="row" style={{ flexDirection: "column", alignItems: "stretch", gap: 14 }}>
            <div className="field">
              <label htmlFor="login-username">Username</label>
              <input
                id="login-username"
                type="text"
                placeholder="admin"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
              />
            </div>
            <div className="field">
              <label htmlFor="login-password">Password</label>
              <input
                id="login-password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <button className="primary" type="submit" disabled={submitting} style={{ justifyContent: "center", marginTop: 4 }}>
              {submitting ? "Signing in…" : "Sign in"}
            </button>
            {(error || googleError) && <div className="alert err" style={{ margin: 0 }}>{error || googleError}</div>}
          </div>
        </form>
        <GoogleSignInButton />
      </section>
      <p className="placeholder" style={{ textAlign: "center", fontSize: 13, marginTop: 14 }}>
        Don't have an account? <Link to="/register">Register</Link>
      </p>
    </div>
  );
}
