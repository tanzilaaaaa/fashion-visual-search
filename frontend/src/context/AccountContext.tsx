import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { me, toApiError } from "../api/client";
import { useAuth } from "./AuthContext";

interface AccountValue {
  /** False when the server has accounts switched off: hearts and the profile are hidden. */
  enabled: boolean;
  isFavorite: (id: string) => boolean;
  toggleFavorite: (id: string) => Promise<void>;
  setFavoriteIds: (ids: string[]) => void;
  avatarColor: string | null;
  setAvatarColor: (c: string) => void;
  notify: (message: string) => void;
}

const AccountContext = createContext<AccountValue | null>(null);

export function AccountProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const enabled = !!user;
  const [ids, setIds] = useState<Set<string>>(new Set());
  const [avatarColor, setAvatarColor] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  const notify = useCallback((message: string) => {
    setToast(message);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(null), 3500);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    me.favoriteIds().then((r) => alive && setIds(new Set(r.ids))).catch(() => undefined);
    me.profile().then((p) => alive && setAvatarColor(p.profile.avatar_color)).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [enabled, user?.id]);

  const isFavorite = useCallback((id: string) => ids.has(id), [ids]);
  const setFavoriteIds = useCallback((list: string[]) => setIds(new Set(list)), []);

  const toggleFavorite = useCallback(
    async (id: string) => {
      const was = ids.has(id);
      // Optimistic: flip now, roll back if the server refuses.
      setIds((prev) => {
        const next = new Set(prev);
        was ? next.delete(id) : next.add(id);
        return next;
      });
      try {
        const r = was ? await me.removeFavorite(id) : await me.addFavorite(id);
        setIds(new Set(r.ids));
        notify(was ? "Removed from favorites" : "Saved to favorites");
      } catch (err) {
        setIds((prev) => {
          const next = new Set(prev);
          was ? next.add(id) : next.delete(id);
          return next;
        });
        notify(toApiError(err).message);
      }
    },
    [ids, notify],
  );

  return (
    <AccountContext.Provider value={{ enabled, isFavorite, toggleFavorite, setFavoriteIds, avatarColor, setAvatarColor, notify }}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center px-4 pb-[calc(1.25rem+env(safe-area-inset-bottom,0px))]">
        {toast && (
          <p role="status" className="pointer-events-auto rounded-full bg-ink px-4 py-2 text-sm font-medium text-canvas shadow-lift animate-fade-up" style={{ animationDuration: "0.2s" }}>
            {toast}
          </p>
        )}
      </div>
    </AccountContext.Provider>
  );
}

const NOOP: AccountValue = {
  enabled: false,
  isFavorite: () => false,
  toggleFavorite: async () => undefined,
  setFavoriteIds: () => undefined,
  avatarColor: null,
  setAvatarColor: () => undefined,
  notify: () => undefined,
};

/** Safe outside the provider (e.g. isolated component tests): features simply stay off. */
export function useAccount() {
  return useContext(AccountContext) ?? NOOP;
}
