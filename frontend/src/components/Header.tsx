import { NavLink, Link } from "react-router-dom";
import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-full px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
    isActive ? "bg-ink text-white" : "text-ink-soft hover:bg-stone-200/70"
  }`;

export function Header() {
  const health = useAsync(() => api.health(), []);
  const { session, logout } = useAuth();
  const ok = health.data?.status === "ok";
  const statusText = health.loading
    ? "Connecting…"
    : ok
      ? `${health.data!.item_count.toLocaleString()} items indexed`
      : "Search server unavailable";

  return (
    <header className="sticky top-0 z-30 border-b border-stone-200/80 bg-canvas/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2 rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-white">
            <svg width="18" height="18" viewBox="0 0 32 32" aria-hidden="true">
              <path d="M11 8l-5 4 3 4 2-1v9h10v-9l2 1 3-4-5-4c-1 2-3 3-5 3s-4-1-5-3z" fill="currentColor" />
            </svg>
          </span>
          <span className="font-display text-xl font-semibold tracking-tight">Lookbook</span>
        </Link>
        <nav className="ml-2 flex items-center gap-1" aria-label="Main">
          <NavLink to="/" end className={navClass}>Search</NavLink>
          <NavLink to="/about" className={navClass}>About</NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <span className="hidden items-center gap-2 text-xs text-ink-muted sm:flex" role="status" title={health.data?.model ?? ""}>
            <span className={`h-2 w-2 rounded-full ${health.loading ? "bg-stone-300" : ok ? "bg-emerald-500" : "bg-amber-500"}`} />
            {statusText}
          </span>
          {session?.auth_enabled && session.authenticated && (
            <button onClick={logout} className="text-sm font-medium text-ink-soft underline-offset-4 hover:underline">
              Sign out
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
