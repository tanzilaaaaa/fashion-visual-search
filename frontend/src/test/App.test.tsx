import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { ApiError } from "../api/client";
import { AuthProvider } from "../context/AuthContext";
import { ThemeProvider } from "../context/ThemeContext";
import { passwordProblem, passwordStrength } from "../pages/AuthPage";
import { filtersResponse } from "./fixtures";

vi.mock("../api/client", async (orig) => {
  const actual = await orig<typeof import("../api/client")>();
  const { makeMe } = await import("./meMock");
  return {
    ...actual,
    me: makeMe(),
    api: {
      me: vi.fn(),
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      showcase: vi.fn(),
      evaluation: vi.fn(),
      health: vi.fn(),
      filters: vi.fn(),
      searchText: vi.fn(),
      searchImage: vi.fn(),
    },
  };
});
const { api } = await import("../api/client");
const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

const SIGNED_OUT = { authenticated: false, auth_enabled: true, user: null };
const USER = { id: 1, name: "Tanzila Tahreem", email: "tanzila@example.com" };
const SIGNED_IN = { authenticated: true, auth_enabled: true, user: USER };

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
  document.documentElement.removeAttribute("data-theme");
  mocked.me.mockResolvedValue(SIGNED_OUT);
  mocked.showcase.mockResolvedValue({ items: [] });
  mocked.evaluation.mockRejectedValue(new ApiError("none", 404, "not_found"));
  mocked.health.mockResolvedValue({ status: "ok", model_loaded: true, index_loaded: true, item_count: 50000 });
  mocked.filters.mockResolvedValue(filtersResponse);
});

describe("landing → auth → app flow", () => {
  it("renders the landing page with sign-up and sign-in calls to action", async () => {
    renderAt("/");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/find the look/i);
    const nav = screen.getByRole("banner");
    await waitFor(() => expect(within(nav).getByRole("link", { name: /get started/i })).toHaveAttribute("href", "/signup"));
    expect(within(nav).getByRole("link", { name: /sign in/i })).toHaveAttribute("href", "/signin");
  });

  it("redirects a signed-out visitor from /app to the sign-in page", async () => {
    renderAt("/app");
    expect(await screen.findByRole("heading", { name: /^sign in$/i })).toBeInTheDocument();
  });

  it("validates the sign-up form before calling the API", async () => {
    renderAt("/signup");
    await userEvent.click(await screen.findByRole("button", { name: /create account/i }));
    expect(screen.getByText(/please enter your name/i)).toBeInTheDocument();
    expect(screen.getByText(/enter a valid email/i)).toBeInTheDocument();
    expect(screen.getByText(/at least 8 characters\./i)).toBeInTheDocument();
    expect(mocked.register).not.toHaveBeenCalled();
  });

  it("shows the server's email_taken error next to the email field", async () => {
    mocked.register.mockRejectedValue(new ApiError("An account with this email already exists.", 409, "email_taken"));
    renderAt("/signup");
    await userEvent.type(await screen.findByLabelText(/full name/i), "Tanzila");
    await userEvent.type(screen.getByLabelText(/^email$/i), "tanzila@example.com");
    await userEvent.type(screen.getByLabelText(/^password$/i), "lookbook123");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    expect(await screen.findByText(/an account with this email already exists/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /sign in instead/i })).toBeInTheDocument();
  });

  it("signs up and lands in the app with a personal greeting", async () => {
    mocked.register.mockResolvedValue(SIGNED_IN);
    renderAt("/signup");
    await userEvent.type(await screen.findByLabelText(/full name/i), "Tanzila Tahreem");
    await userEvent.type(screen.getByLabelText(/^email$/i), "tanzila@example.com");
    await userEvent.type(screen.getByLabelText(/^password$/i), "lookbook123");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    expect(mocked.register).toHaveBeenCalledWith("Tanzila Tahreem", "tanzila@example.com", "lookbook123");
    expect(await screen.findByText(/, Tanzila$/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /account menu for tanzila tahreem/i })).toHaveTextContent("TT");
  });

  it("shows invalid credentials on sign in", async () => {
    mocked.login.mockRejectedValue(new ApiError("Incorrect email or password.", 401, "invalid_credentials"));
    renderAt("/signin");
    await userEvent.type(await screen.findByLabelText(/^email$/i), "tanzila@example.com");
    await userEvent.type(screen.getByLabelText(/^password$/i), "wrongpass1");
    await userEvent.click(screen.getByRole("button", { name: /^sign in$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/incorrect email or password/i);
  });

  it("toggles password visibility", async () => {
    renderAt("/signin");
    const pw = await screen.findByLabelText(/^password$/i);
    expect(pw).toHaveAttribute("type", "password");
    await userEvent.click(screen.getByRole("button", { name: /show password/i }));
    expect(pw).toHaveAttribute("type", "text");
  });
});

describe("theme switcher", () => {
  it("applies and remembers the chosen theme", async () => {
    renderAt("/");
    await userEvent.click(within(screen.getByRole("banner")).getByRole("button", { name: /change theme/i }));
    await userEvent.click(screen.getByRole("menuitemradio", { name: /noir/i }));
    expect(document.documentElement.dataset.theme).toBe("noir");
    expect(localStorage.getItem("lookbook.theme")).toBe("noir");
    await userEvent.click(within(screen.getByRole("banner")).getByRole("button", { name: /theme: noir/i }));
    expect(screen.getByRole("menuitemradio", { name: /noir/i })).toHaveAttribute("aria-checked", "true");
  });
});

describe("password helpers", () => {
  it("mirror the API policy", () => {
    expect(passwordProblem("lookbook123")).toBeNull();
    expect(passwordProblem("short1")).toMatch(/8 characters/);
    expect(passwordProblem("lettersonly")).toMatch(/letter and one number/);
    expect(passwordStrength("")).toBe(0);
    expect(passwordStrength("Lookbook-2026!x")).toBe(4);
  });
});
