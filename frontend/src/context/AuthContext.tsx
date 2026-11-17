import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api } from "../api/client";
import type { SessionResponse } from "../api/types";

interface AuthValue {
  session: SessionResponse | null;
  checking: boolean;
  login: (u: string, p: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    api
      .me()
      .then(setSession)
      // If the server is unreachable, don't block the UI behind a login wall;
      // the search page will show the connection error instead.
      .catch(() => setSession({ authenticated: true, auth_enabled: false }))
      .finally(() => setChecking(false));
  }, []);

  const login = useCallback(async (u: string, p: string) => setSession(await api.login(u, p)), []);
  const logout = useCallback(async () => {
    await api.logout().catch(() => undefined);
    setSession((s) => (s ? { ...s, authenticated: false, username: null } : s));
  }, []);

  return <AuthContext.Provider value={{ session, checking, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Only gates routes when the backend has AUTH_ENABLED=true. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { session, checking } = useAuth();
  const location = useLocation();
  if (checking) return null;
  if (session?.auth_enabled && !session.authenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}
