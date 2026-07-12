import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Icon from "./Icon";
import { fuzzyMatch } from "../lib/fuzzy";
import { truncate } from "../lib/format";

export default function CommandPalette({ open, onClose, navLinks }) {
  const [query, setQuery] = useState("");
  const [recent, setRecent] = useState([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActiveIndex(0);
    fetch("/api/investigations?limit=8")
      .then((r) => r.json())
      .then(setRecent)
      .catch(() => setRecent([]));
    const t = setTimeout(() => inputRef.current?.focus(), 10);
    return () => clearTimeout(t);
  }, [open]);

  const allItems = useMemo(() => {
    const navItems = navLinks.map((l) => ({ type: "nav", id: l.to, label: l.label, icon: l.icon, to: l.to }));
    const recentItems = recent.map((r) => ({
      type: "investigation",
      id: r.id,
      label: `${r.source}${r.source_ref ? " " + r.source_ref : ""} — ${truncate(r.alert_text || "", 60)}`,
      icon: "search",
      to: `/investigations/${r.id}`,
    }));
    return [...navItems, ...recentItems];
  }, [navLinks, recent]);

  const results = useMemo(() => {
    if (!query.trim()) return allItems;
    return allItems
      .map((item) => ({ item, score: fuzzyMatch(query, item.label) }))
      .filter((x) => x.score != null)
      .sort((a, b) => b.score - a.score)
      .map((x) => x.item);
  }, [query, allItems]);

  useEffect(() => setActiveIndex(0), [query]);

  function go(item) {
    navigate(item.to);
    onClose();
  }

  function onKeyDown(e) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (results[activeIndex]) go(results[activeIndex]);
    } else if (e.key === "Escape") {
      onClose();
    }
  }

  if (!open) return null;

  return (
    <div className="palette-scrim" onClick={onClose}>
      <div
        className="palette"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
      >
        <div className="palette-input-row">
          <Icon name="search" size={16} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Jump to a page or investigation…"
            aria-label="Search"
            autoComplete="off"
          />
          <kbd>Esc</kbd>
        </div>
        <div className="palette-results" role="listbox">
          {results.length === 0 && <div className="palette-empty">No matches.</div>}
          {results.map((item, i) => (
            <div
              key={item.type + item.id}
              role="option"
              aria-selected={i === activeIndex}
              className={"palette-item" + (i === activeIndex ? " active" : "")}
              onMouseEnter={() => setActiveIndex(i)}
              onClick={() => go(item)}
            >
              <Icon name={item.icon} size={15} />
              <span className="palette-item-label">{item.label}</span>
              {item.type === "investigation" && <span className="palette-item-tag">investigation</span>}
            </div>
          ))}
        </div>
        <div className="palette-footer">
          <span>
            <kbd>↑</kbd>
            <kbd>↓</kbd> navigate
          </span>
          <span>
            <kbd>Enter</kbd> open
          </span>
          <span>
            <kbd>Esc</kbd> close
          </span>
        </div>
      </div>
    </div>
  );
}
