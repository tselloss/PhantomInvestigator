import { useMemo, useRef } from "react";
import "./CircularText.css";

const HOVER_FACTOR = {
  slowDown: 2,
  speedUp: 1 / 4,
  pause: null,
  goBonkers: 1 / 20,
};

export default function CircularText({
  text,
  spinDuration = 20,
  onHover = "speedUp",
  size = 120,
  className = "",
  children,
}) {
  const wrapRef = useRef(null);
  const elRef = useRef(null);
  const letters = useMemo(() => Array.from(text), [text]);
  const radius = size / 2 - 10;

  function applyDuration(seconds) {
    const el = elRef.current;
    if (!el) return;
    el.style.animationDuration = `${seconds}s`;
  }

  function handleEnter() {
    const el = elRef.current;
    if (!el || !onHover) return;
    if (onHover === "pause") {
      el.style.animationPlayState = "paused";
      return;
    }
    const factor = HOVER_FACTOR[onHover] ?? 1;
    applyDuration(spinDuration * factor);
    if (onHover === "goBonkers") wrapRef.current?.style.setProperty("--ct-scale", "0.85");
  }

  function handleLeave() {
    const el = elRef.current;
    if (!el) return;
    el.style.animationPlayState = "running";
    wrapRef.current?.style.setProperty("--ct-scale", "1");
    applyDuration(spinDuration);
  }

  return (
    <div
      ref={wrapRef}
      className={`circular-text-wrap ${className}`}
      style={{ width: size, height: size }}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      <div
        ref={elRef}
        className="circular-text"
        style={{ animationDuration: `${spinDuration}s` }}
      >
        {letters.map((letter, i) => {
          const angle = (360 / letters.length) * i;
          return (
            <span key={i} style={{ transform: `rotate(${angle}deg) translate(0, -${radius}px)` }}>
              {letter}
            </span>
          );
        })}
      </div>
      {children && <div className="circular-text-center">{children}</div>}
    </div>
  );
}
