import { NavLink } from "react-router-dom";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { ChartIcon, SearchIcon, UserIcon } from "./Icons";
import { useAccount } from "../context/AccountContext";
import { Logo } from "./Logo";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { UserMenu } from "./UserMenu";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `inline-flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-sm font-medium transition sm:px-3.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
    isActive ? "bg-ink text-canvas" : "text-ink-soft hover:bg-surface-2 hover:text-ink"
  }`;

export function AppHeader() {
  const { enabled } = useAccount();
  const health = useAsync(() => api.health(), []);
  const ok = health.data?.status === "ok";
  const statusText = health.loading
    ? "Connecting…"
    : ok
      ? `${health.data!.item_count.toLocaleString()} items`
      : "Server offline";

  return (
    <header className="glass sticky top-0 z-40 border-x-0 border-t-0">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-2 px-4 sm:gap-3 sm:px-6">
        <Logo to="/app" compact />
        <nav className="ml-0 flex min-w-0 items-center gap-0.5 sm:ml-4 sm:gap-1" aria-label="Main">
          <NavLink to="/app" end className={navClass}>
            <SearchIcon width={15} height={15} /> <span className="hidden sm:inline">Search</span>
          </NavLink>
          <NavLink to="/app/insights" className={navClass}>
            <ChartIcon width={15} height={15} /> <span className="hidden sm:inline">Insights</span>
          </NavLink>
          {enabled && (
            <NavLink to="/app/profile" className={navClass}>
              <UserIcon width={15} height={15} /> <span className="hidden sm:inline">Profile</span>
            </NavLink>
          )}
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
