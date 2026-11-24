import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { ApiError } from "../api/client";
import { AuthProvider } from "../context/AuthContext";
import { ThemeProvider } from "../context/ThemeContext";
import { filtersResponse, item } from "./fixtures";
import { profileFixture } from "./meMock";

vi.mock("../api/client", async (orig) => {
  const actual = await orig<typeof import("../api/client")>();
  const { makeMe } = await import("./meMock");
  return {
    ...actual,
    me: makeMe(),
    api: { me: vi.fn(), logout: vi.fn(), showcase: vi.fn(), evaluation: vi.fn(), health: vi.fn(), filters: vi.fn(), searchText: vi.fn(), searchImage: vi.fn(), item: vi.fn(), similar: vi.fn(), recommendations: vi.fn() },
  };
});
const client = await import("../api/client");
const api = client.api as unknown as Record<string, ReturnType<typeof vi.fn>>;
const me = client.me as unknown as Record<string, ReturnType<typeof vi.fn>>;

const USER = { id: 1, name: "Tanzila Tahreem", email: "tanzila@example.com" };
const saved = { ...item(1), saved_at: 1_763_000_100 };

function renderAt(path: string) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.me.mockResolvedValue({ authenticated: true, auth_enabled: true, user: USER });
  api.health.mockResolvedValue({ status: "ok", model_loaded: true, index_loaded: true, item_count: 50000 });
  api.filters.mockResolvedValue(filtersResponse);
  api.showcase.mockResolvedValue({ items: [] });
  api.evaluation.mockRejectedValue(new ApiError("none", 404, "not_found"));
  me.profile.mockResolvedValue(profileFixture({ stats: { favorites: 1, collections: 0, searches: 2 } }));
  me.favoriteIds.mockResolvedValue({ ids: [saved.item_id] });
  me.favorites.mockResolvedValue({ total: 1, items: [saved] });
  me.history.mockResolvedValue({ entries: [] });
  me.recommendations.mockResolvedValue({ sections: [], has_favorites: false, has_interests: false });
});

describe("ProfilePage", () => {
  it("shows the profile header, stats and tabs, with an onboarding state for picks", async () => {
    renderAt("/app/profile");
    expect(await screen.findByRole("heading", { level: 1, name: "Tanzila Tahreem" })).toBeInTheDocument();
    expect(await screen.findByText("Loves denim.")).toBeInTheDocument();
    expect(screen.getByText("Bengaluru")).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: /profile sections/i });
    for (const t of ["For you", "Favorites", "Collections", "Interests", "Recent searches", "Settings"]) {
      expect(within(nav).getByRole("button", { name: t })).toBeInTheDocument();
    }
    expect(await screen.findByText(/your picks will appear here/i)).toBeInTheDocument();
  });

  it("lists favorites and rolls a failed unsave back", async () => {
    me.removeFavorite.mockRejectedValue(new ApiError("Couldn't reach the server.", 0, "network_error"));
    renderAt("/app/profile#favorites");
    const heart = await screen.findByRole("button", { name: /remove .* from favorites/i });
    expect(heart).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(heart);
    expect(await screen.findByText(/couldn't reach the server/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /remove .* from favorites/i })).toHaveAttribute("aria-pressed", "true");
  });

  it("saves interests picked as chips", async () => {
    me.setInterests.mockResolvedValue({ categories: ["skirt"], colours: ["red"], styles: ["minimal"] });
    renderAt("/app/profile#interests");
    await userEvent.click(await screen.findByRole("button", { name: "Skirt" }));
    await userEvent.click(screen.getByRole("button", { name: "Red" }));
    await userEvent.click(screen.getByRole("button", { name: "Minimal" }));
    await userEvent.click(screen.getByRole("button", { name: /save interests/i }));
    await waitFor(() =>
      expect(me.setInterests).toHaveBeenCalledWith({ categories: ["skirt"], colours: ["red"], styles: ["minimal"] }),
    );
    expect(await screen.findByText(/interests saved/i)).toBeInTheDocument();
  });

  it("only deletes the account after the email is typed", async () => {
    me.deleteAccount.mockResolvedValue(undefined);
    api.logout.mockResolvedValue({ authenticated: false, auth_enabled: true, user: null });
    renderAt("/app/profile#settings");
    await userEvent.click(await screen.findByRole("button", { name: /delete my account/i }));
    const confirm = screen.getByRole("button", { name: /delete forever/i });
    await userEvent.type(screen.getByLabelText(/^password$/i), "lookbook123");
    expect(confirm).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/type tanzila@example.com to confirm/i), "tanzila@example.com");
    expect(confirm).toBeEnabled();
    await userEvent.click(confirm);
    await waitFor(() => expect(me.deleteAccount).toHaveBeenCalledWith("lookbook123"));
  });

  it("shows account-synced searches as chips on the search page", async () => {
    me.history.mockResolvedValue({ entries: [{ id: 2, query: "blue denim jacket", created_at: 1 }, { id: 1, query: "red dress", created_at: 0 }] });
    renderAt("/app");
    expect(await screen.findByRole("button", { name: "blue denim jacket" })).toBeInTheDocument();
    expect(screen.getByText("Recent:")).toBeInTheDocument();
  });

  it("links to the profile from the account menu", async () => {
    renderAt("/app");
    await userEvent.click(await screen.findByRole("button", { name: /account menu for tanzila tahreem/i }));
    expect(screen.getByRole("menuitem", { name: /your profile/i })).toHaveAttribute("href", "/app/profile");
  });
});
