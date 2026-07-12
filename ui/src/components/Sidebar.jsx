import { Link, NavLink } from "react-router-dom";
import Icon from "./Icon";
import { NAV_LINKS } from "../lib/navLinks";

const GITHUB_URL = "https://github.com/tselloss";
const COFFEE_URL = "https://buymeacoffee.com/tsellosskr";

export default function Sidebar({ collapsed, onToggleCollapse, mobileOpen, onCloseMobile }) {
  return (
    <>
      {mobileOpen && <div className="sidebar-scrim" onClick={onCloseMobile} aria-hidden="true" />}
      <aside className={"sidebar" + (collapsed ? " collapsed" : "") + (mobileOpen ? " mobile-open" : "")}>
        <div className="sidebar-brand">
          <Link to="/dashboard" className="brand" onClick={onCloseMobile}>
            <span className="brand-mark">
              <Icon name="ghost" size={18} />
            </span>
            {!collapsed && <span className="sidebar-wordmark brand-shine">Phantom Investigator</span>}
          </Link>
        </div>

        <nav className="sidebar-nav">
          {NAV_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              onClick={onCloseMobile}
              className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}
              title={collapsed ? link.label : undefined}
            >
              <Icon name={link.icon} size={17} />
              {!collapsed && <span>{link.label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          {!collapsed && (
            <>
              <a className="sidebar-link secondary" href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
                <span>GitHub</span>
              </a>
              <a className="sidebar-link secondary" href={COFFEE_URL} target="_blank" rel="noopener noreferrer">
                <span>Support the project</span>
              </a>
            </>
          )}
          <button
            className="sidebar-collapse-btn"
            onClick={onToggleCollapse}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <Icon name="chevron" size={15} style={{ transform: collapsed ? "none" : "rotate(180deg)" }} />
          </button>
        </div>
      </aside>
    </>
  );
}
