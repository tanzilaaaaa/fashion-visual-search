/** Initials avatar on a colour the user picks (stored on the profile). */
export const AVATAR_GRADIENTS: Record<string, [string, string]> = {
  rose: ["#be123c", "#fb7185"],
  amber: ["#b45309", "#f59e0b"],
  emerald: ["#047857", "#34d399"],
  sky: ["#0369a1", "#38bdf8"],
  violet: ["#6d28d9", "#a78bfa"],
  slate: ["#334155", "#94a3b8"],
  gold: ["#8a6d1f", "#d4af37"],
  coral: ["#c2410c", "#fb923c"],
};

export const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("") || "?";

export function Avatar({ name, color, size = 36 }: { name: string; color?: string | null; size?: number }) {
  const [a, b] = AVATAR_GRADIENTS[color ?? ""] ?? AVATAR_GRADIENTS.rose!;
  return (
    <span
      aria-hidden="true"
      className="grid shrink-0 place-items-center rounded-full font-bold text-white shadow-glow"
      style={{ width: size, height: size, fontSize: size * 0.38, background: `linear-gradient(135deg, ${a}, ${b})` }}
    >
      {initials(name)}
    </span>
  );
}
