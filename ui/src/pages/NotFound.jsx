import { Link } from "react-router-dom";
import Icon from "../components/Icon";
import Button from "../components/Button";
import { useAuth } from "../context/AuthContext";

export default function NotFound() {
  const { user } = useAuth();

  return (
    <div className="auth-page" style={{ maxWidth: 420, margin: "0 auto", textAlign: "center" }}>
      <span className="brand-mark hero-mark hero-mark-float" style={{ width: 64, height: 64, margin: "0 auto 20px" }}>
        <Icon name="ghost" size={34} />
      </span>
      <h1 style={{ fontSize: 24, fontWeight: 800, margin: "0 0 8px", letterSpacing: "-0.01em" }}>Nothing here</h1>
      <p className="placeholder" style={{ marginBottom: 24 }}>
        This page doesn't exist, or you don't have access to it.
      </p>
      <Link to={user ? "/dashboard" : "/"}>
        <Button variant="primary">{user ? "Back to Dashboard" : "Back home"}</Button>
      </Link>
    </div>
  );
}
