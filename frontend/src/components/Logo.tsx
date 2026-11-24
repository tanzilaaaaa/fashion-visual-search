import { Link } from "react-router-dom";

export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <span className="bg-gradient-accent grid place-items-center rounded-xl text-on-accent shadow-glow" style={{ width: size, height: size }}>
      <svg width={size * 0.56} height={size * 0.56} viewBox="0 0 32 32" aria-hidden="true">
        <path d="M11 8l-5 4 3 4 2-1v9h10v-9l2 1 3-4-5-4c-1 2-3 3-5 3s-4-1-5-3z" fill="currentColor" />
      </svg>
    </span>
  );
}

export function Logo({ to = "/", compact = false }: { to?: string; compact?: boolean }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-2.5 rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
      aria-label="Lookbook home"
    >
      <LogoMark />
      <span className={`font-display text-xl font-semibold tracking-tight text-ink ${compact ? "hidden sm:inline" : ""}`}>Lookbook</span>
    </Link>
  );
}
