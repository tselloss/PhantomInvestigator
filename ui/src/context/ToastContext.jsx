import { createContext, useCallback, useContext, useRef, useState } from "react";
import Icon from "../components/Icon";

const ToastContext = createContext(null);
let idSeq = 0;

const ICONS = { ok: "check", warn: "zap", err: "x" };

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef({});

  const dismiss = useCallback((id) => {
    setToasts((t) => t.filter((x) => x.id !== id));
    clearTimeout(timers.current[id]);
    delete timers.current[id];
  }, []);

  const show = useCallback(
    (message, { type = "ok", duration = 4500 } = {}) => {
      const id = ++idSeq;
      setToasts((t) => [...t, { id, message, type }]);
      timers.current[id] = setTimeout(() => dismiss(id), duration);
      return id;
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={{ show, dismiss }}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={"toast " + t.type} onClick={() => dismiss(t.id)}>
            <Icon name={ICONS[t.type] || "check"} size={15} />
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
