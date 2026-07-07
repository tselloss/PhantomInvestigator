import { NavLink, Outlet } from "react-router-dom";
import StatusPill from "./StatusPill";
import { useAuth } from "../context/AuthContext";

const NAV_LINKS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/investigate", label: "Investigate" },
  { to: "/investigations", label: "Investigations" },
  { to: "/runbooks", label: "Runbooks" },
  { to: "/settings/integrations", label: "Integrations" },
  { to: "/demo", label: "Demo & testing" },
];

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <>
      <header>
        <div className="row" style={{ gap: 24 }}>
          <h1>👻 Phantom Investigator</h1>
          <nav className="row" style={{ gap: 4 }}>
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="row">
          <StatusPill />
          {user && (
            <button onClick={logout} title={`Logged in as ${user}`}>
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
