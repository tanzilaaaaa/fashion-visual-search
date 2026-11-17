import { NavLink } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { ChartIcon, SearchIcon } from "./Icons";
import { Logo } from "./Logo";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { UserMenu } from "./UserMenu";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
    isActive ? "bg-ink text-canvas" : "text-ink-soft hover:bg-surface-2 hover:text-ink"
  }`;

export function AppHeader() {
  const health = useAsync(() => api.health(), []);
  const ok = health.data?.status === "ok";
  const statusText = health.loading
    ? "Connecting…"
    : ok
      ? `${health.data!.item_count.toLocaleString()} items`
      : "Server offline";

  return (
    <header className="glass sticky top-0 z-40 border-x-0 border-t-0">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6">
        <Logo to="/app" />
        <nav className="ml-1 flex items-center gap-1 sm:ml-4" aria-label="Main">
          <NavLink to="/app" end className={navClass}>
            <SearchIcon width={15} height={15} /> <span className="hidden sm:inline">Search</span>
          </NavLink>
          <NavLink to="/app/insights" className={navClass}>
            <ChartIcon width={15} height={15} /> <span className="hidden sm:inline">Insights</span>
          </NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          <span
            className="hidden items-center gap-2 rounded-full border border-line bg-surface/60 px-3 py-1 text-xs text-ink-muted md:flex"
            role="status"
            title={health.data?.model ?? ""}
          >
            <span className={`h-2 w-2 rounded-full ${health.loading ? "bg-ink-muted" : ok ? "bg-success" : "bg-danger"}`} />
            {statusText}
          </span>
          <ThemeSwitcher />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
