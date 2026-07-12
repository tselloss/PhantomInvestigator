import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

const CHORDS = {
  d: "/dashboard",
  i: "/investigate",
  l: "/investigations",
  c: "/clients",
  r: "/runbooks",
  p: "/settings/profile",
  s: "/settings/integrations",
};

function isTypingTarget(el) {
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

export default function useKeyboardShortcuts({ onOpenPalette, disabled = false }) {
  const navigate = useNavigate();
  const pendingG = useRef(false);
  const timerRef = useRef(null);

  useEffect(() => {
    function onKeyDown(e) {
      if (disabled) return;
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenPalette();
        return;
      }
      if (isTypingTarget(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;

      if (pendingG.current) {
        pendingG.current = false;
        clearTimeout(timerRef.current);
        const dest = CHORDS[e.key.toLowerCase()];
        if (dest) {
          e.preventDefault();
          navigate(dest);
        }
        return;
      }
      if (e.key.toLowerCase() === "g") {
        pendingG.current = true;
        timerRef.current = setTimeout(() => {
          pendingG.current = false;
        }, 800);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      clearTimeout(timerRef.current);
    };
  }, [navigate, onOpenPalette, disabled]);
}
