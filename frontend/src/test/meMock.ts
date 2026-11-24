import { vi } from "vitest";
import type { ProfileResponse } from "../api/types";

export const profileFixture = (over: Partial<ProfileResponse> = {}): ProfileResponse => ({
  user: { id: 1, name: "Tanzila Tahreem", email: "tanzila@example.com" },
  profile: { bio: "Loves denim.", location: "Bengaluru", avatar_color: "violet" },
  interests: { categories: [], colours: [], styles: [] },
  stats: { favorites: 0, collections: 0, searches: 0 },
  member_since: 1_763_000_000,
  avatar_colors: ["rose", "amber", "emerald", "sky", "violet", "slate", "gold", "coral"],
  style_presets: ["minimal", "streetwear", "boho", "formal", "sporty", "vintage", "casual", "party"],
  ...over,
});

/** A `me` API double with harmless defaults; tests override individual calls. */
export function makeMe() {
  return {
    profile: vi.fn().mockResolvedValue(profileFixture()),
    updateProfile: vi.fn(),
    setInterests: vi.fn(),
    favorites: vi.fn().mockResolvedValue({ total: 0, items: [] }),
    favoriteIds: vi.fn().mockResolvedValue({ ids: [] }),
    addFavorite: vi.fn(),
    removeFavorite: vi.fn(),
    collections: vi.fn().mockResolvedValue({ collections: [] }),
    collection: vi.fn(),
    createCollection: vi.fn(),
    renameCollection: vi.fn(),
    deleteCollection: vi.fn(),
    addToCollection: vi.fn(),
    removeFromCollection: vi.fn(),
    history: vi.fn().mockResolvedValue({ entries: [] }),
    clearHistory: vi.fn().mockResolvedValue(undefined),
    deleteHistory: vi.fn().mockResolvedValue(undefined),
    recommendations: vi.fn().mockResolvedValue({ sections: [], has_favorites: false, has_interests: false }),
    changeEmail: vi.fn(),
    changePassword: vi.fn(),
    deleteAccount: vi.fn(),
  };
}
