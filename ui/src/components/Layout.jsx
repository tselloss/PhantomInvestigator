import { NavLink, Outlet } from "react-router-dom";
import Icon from "./Icon";
import StatusPill from "./StatusPill";
import { useAuth } from "../context/AuthContext";

const NAV_LINKS = [
  { to: "/dashboard", label: "Dashboard", end: true, icon: "home" },
  { to: "/investigate", label: "Investigate", icon: "search" },
  { to: "/investigations", label: "Investigations", icon: "list" },
  { to: "/clients", label: "Clients", icon: "users" },
  { to: "/runbooks", label: "Runbooks", icon: "book" },
  { to: "/settings/integrations", label: "Integrations", icon: "zap" },
  { to: "/demo", label: "Demo & testing", icon: "flask" },
];

const GITHUB_URL = "https://github.com/tselloss";
const COFFEE_URL = "https://buymeacoffee.com/tsellosskr";

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <>
      <header>
        <div className="row" style={{ gap: 20 }}>
          <div className="brand">
            <span className="brand-mark">👻</span>
            <h1>Phantom Investigator</h1>
          </div>
          <nav className="row" style={{ gap: 2 }}>
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
              >
                <Icon name={link.icon} size={15} />
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="row">
          <a className="nav-link" href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
            GitHub
          </a>
          <a className="nav-link" href={COFFEE_URL} target="_blank" rel="noopener noreferrer">
            ☕ Buy me a coffee
          </a>
          <StatusPill />
          {user && (
            <button onClick={logout} title={`Logged in as ${user.username}`}>
              <Icon name="logOut" size={14} />
              Log out
            </button>
          )}
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </>
  );
}
