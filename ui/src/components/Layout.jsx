import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Icon from "./Icon";
import Threads from "./Threads";
import Sidebar from "./Sidebar";
import CommandPalette from "./CommandPalette";
import TermsGate from "./TermsGate";
import useKeyboardShortcuts from "../hooks/useKeyboardShortcuts";
import { useAuth } from "../context/AuthContext";
import { NAV_LINKS } from "../lib/navLinks";

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("sidebar-collapsed") === "1");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    localStorage.setItem("sidebar-collapsed", collapsed ? "1" : "0");
  }, [collapsed]);

  // TermsGate below renders on top of everything once tosAccepted is false,
  // but a fixed-position overlay alone doesn't stop keyboard shortcuts or
  // page-level effects from still running behind it -- gate those too so
  // it's a real block, not just a visual one.
  const gateOpen = !!user && user.tosAccepted === false;

  useKeyboardShortcuts({ onOpenPalette: () => setPaletteOpen(true), disabled: gateOpen });

  const activeLink = NAV_LINKS.find((l) => (l.end ? location.pathname === l.to : location.pathname.startsWith(l.to)));
  const title = activeLink?.label || "Phantom Investigator";

  return (
    <div className="app-shell">
      <div className="app-ambient-bg" aria-hidden="true">
        <Threads color={[91, 140, 255]} amplitude={0.4} distance={0.1} />
      </div>

      <Sidebar
        collapsed={collapsed && !mobileOpen}
        onToggleCollapse={() => setCollapsed((c) => !c)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <div className="app-main-col">
        <header className="topbar">
          <div className="row" style={{ gap: 12 }}>
            <button
              className="sidebar-toggle-mobile"
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen((v) => !v)}
            >
              <Icon name={mobileOpen ? "x" : "menu"} size={18} />
            </button>
            <h1 className="topbar-title">{title}</h1>
          </div>
          <div className="row" style={{ gap: 10 }}>
            <button className="palette-trigger" onClick={() => setPaletteOpen(true)} disabled={gateOpen}>
              <Icon name="search" size={14} />
              Search
              <kbd>{isMac ? "⌘" : "Ctrl"} K</kbd>
            </button>
            {user && (
              <button onClick={logout} title={`Logged in as ${user.username}`}>
                <Icon name="logOut" size={14} />
              </button>
            )}
          </div>
        </header>

        <main>{gateOpen ? null : <Outlet />}</main>
      </div>

      <CommandPalette open={paletteOpen && !gateOpen} onClose={() => setPaletteOpen(false)} navLinks={NAV_LINKS} />
      <TermsGate />
    </div>
  );
}
