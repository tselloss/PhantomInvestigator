import { createContext, useContext, useEffect, useState } from "react";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined); // undefined = checking, null = logged out, {id, username} = logged in
  const [error, setError] = useState(null);

  async function checkSession() {
    try {
      const res = await fetch("/auth/me");
      if (res.ok) {
        const data = await res.json();
        setUser({ id: data.id, username: data.username, tosAccepted: data.tos_accepted });
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    }
  }

  useEffect(() => {
    checkSession();
  }, []);

  async function login(username, password) {
    setError(null);
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      setError("Invalid username or password");
      return false;
    }
    await checkSession();
    return true;
  }

  async function register(username, password, acceptTerms) {
    setError(null);
    const res = await fetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, accept_terms: acceptTerms }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      setError(res.status === 409 ? "That username is already taken" : detail.detail || "Registration failed");
      return false;
    }
    await checkSession();
    return true;
  }

  async function logout() {
    await fetch("/auth/logout", { method: "POST" });
    setUser(null);
  }

  async function acceptTerms() {
    const res = await fetch("/auth/accept-terms", { method: "POST" });
    if (!res.ok) return false;
    setUser((u) => (u ? { ...u, tosAccepted: true } : u));
    return true;
  }

  return (
    <AuthContext.Provider
      value={{ user, error, login, register, logout, acceptTerms, checking: user === undefined }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
