import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { toApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";

export function LoginPage() {
  const { session, login } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/";
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (session && (!session.auth_enabled || session.authenticated)) return <Navigate to={from} replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-sm px-4 py-20">
      <h1 className="font-display text-2xl font-semibold">Sign in to the demo</h1>
      <p className="mt-1 text-sm text-ink-muted">This deployment is protected with a shared demo login.</p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <div>
          <label htmlFor="u" className="mb-1 block text-sm font-medium">Username</label>
          <input id="u" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required
            className="w-full rounded-lg border border-stone-300 px-3 py-2 focus:border-ink focus:outline-none" />
        </div>
        <div>
          <label htmlFor="p" className="mb-1 block text-sm font-medium">Password</label>
          <input id="p" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required
            className="w-full rounded-lg border border-stone-300 px-3 py-2 focus:border-ink focus:outline-none" />
        </div>
        {error && <p role="alert" className="text-sm text-accent">{error}</p>}
        <button disabled={busy} className="w-full rounded-lg bg-ink py-2.5 text-sm font-semibold text-white hover:bg-black disabled:opacity-70">
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
