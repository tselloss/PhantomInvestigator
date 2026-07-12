import { Component } from "react";
import Icon from "./Icon";
import Button from "./Button";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Unhandled UI error:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="auth-page" style={{ maxWidth: 420, margin: "0 auto", textAlign: "center" }}>
          <span className="brand-mark hero-mark" style={{ width: 64, height: 64, margin: "0 auto 20px" }}>
            <Icon name="ghost" size={34} />
          </span>
          <h1 style={{ fontSize: 24, fontWeight: 800, margin: "0 0 8px", letterSpacing: "-0.01em" }}>Something broke</h1>
          <p className="placeholder" style={{ marginBottom: 24 }}>
            An unexpected error occurred. Reloading usually fixes it.
          </p>
          <Button variant="primary" onClick={() => window.location.reload()}>
            Reload
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
