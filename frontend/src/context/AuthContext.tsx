import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api } from "../api/client";
import type { SessionResponse, User } from "../api/types";

interface AuthValue {
  session: SessionResponse | null;
  user: User | null;
  checking: boolean;
  /** True when the user may use the app (signed in, or the server has auth disabled). */
  allowed: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
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
      // Server unreachable: treat as signed out; pages show the connection error.
      .catch(() => setSession({ authenticated: false, auth_enabled: true, user: null }))
      .finally(() => setChecking(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => setSession(await api.login(email, password)), []);
  const register = useCallback(
    async (name: string, email: string, password: string) => setSession(await api.register(name, email, password)),
    [],
  );
  const logout = useCallback(async () => {
    const next = await api.logout().catch(() => null);
    setSession(next ?? { authenticated: false, auth_enabled: true, user: null });
  }, []);

  const allowed = !!session && (session.authenticated || !session.auth_enabled);
  return (
    <AuthContext.Provider value={{ session, user: session?.user ?? null, checking, allowed, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Gate for /app routes: unauthenticated visitors are sent to sign in, then returned. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { checking, allowed } = useAuth();
  const location = useLocation();
  if (checking) {
    return (
      <div className="grid min-h-[60vh] place-items-center" role="status" aria-label="Checking your session">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-accent" />
      </div>
    );
  }
  if (!allowed) return <Navigate to="/signin" replace state={{ from: location.pathname + location.hash }} />;
  return <>{children}</>;
}
