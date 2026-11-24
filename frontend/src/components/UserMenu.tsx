import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAccount } from "../context/AccountContext";
import { useAuth } from "../context/AuthContext";
import { Avatar } from "./Avatar";
import { HeartIcon, LogOutIcon, UserIcon } from "./Icons";

export { initials } from "./Avatar";

export function UserMenu() {
  const { user, logout } = useAuth();
  const { avatarColor } = useAccount();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null; // auth disabled on the server: nothing to show

  const item =
    "flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-ink-soft transition hover:bg-surface-2 hover:text-ink focus:bg-surface-2 focus:outline-none";
  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${user.name}`}
        onClick={() => setOpen((v) => !v)}
        className="rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        <Avatar name={user.name} color={avatarColor} />
      </button>
      {open && (
        <div role="menu" className="glass absolute right-0 z-50 mt-2 w-64 rounded-2xl p-2 shadow-lift animate-fade-up" style={{ animationDuration: "0.2s" }}>
          <div className="flex items-center gap-3 px-3 py-2">
            <Avatar name={user.name} color={avatarColor} size={40} />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink">{user.name}</p>
              <p className="truncate text-xs text-ink-muted">{user.email}</p>
            </div>
          </div>
          <div className="my-1 h-px bg-line" />
          <Link role="menuitem" to="/app/profile" onClick={() => setOpen(false)} className={item}>
            <UserIcon width={16} height={16} /> Your profile
          </Link>
          <Link role="menuitem" to="/app/profile#favorites" onClick={() => setOpen(false)} className={item}>
            <HeartIcon width={16} height={16} /> Favorites
          </Link>
          <button
            role="menuitem"
            type="button"
            onClick={async () => {
              await logout();
              navigate("/", { replace: true });
            }}
            className={item}
          >
            <LogOutIcon width={16} height={16} /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}
