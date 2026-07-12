import { useState } from "react";
import Icon from "./Icon";

// A password-style input that reveals its plaintext only while the reveal
// button is actively held (mouse/touch down) — never a persistent toggle.
// Only ever shows what the operator is currently typing in their own
// browser; the server never sends a saved secret back to reveal.
export default function RevealInput({ value, onChange, placeholder }) {
  const [revealed, setRevealed] = useState(false);

  return (
    <div className="reveal-input">
      <input type={revealed ? "text" : "password"} placeholder={placeholder} value={value} onChange={onChange} />
      <button
        type="button"
        className="reveal-input-btn"
        tabIndex={-1}
        aria-label="Hold to reveal"
        onMouseDown={() => setRevealed(true)}
        onMouseUp={() => setRevealed(false)}
        onMouseLeave={() => setRevealed(false)}
        onTouchStart={() => setRevealed(true)}
        onTouchEnd={() => setRevealed(false)}
      >
        <Icon name={revealed ? "eyeOff" : "eye"} size={14} />
      </button>
    </div>
  );
}
