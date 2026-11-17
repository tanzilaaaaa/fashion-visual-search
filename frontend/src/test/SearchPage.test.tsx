import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { SearchProvider } from "../context/SearchContext";
import { SearchPage } from "../pages/SearchPage";
import { filtersResponse, searchResponse } from "./fixtures";

vi.mock("../api/client", async (orig) => {
  const actual = await orig<typeof import("../api/client")>();
  return {
    ...actual,
    api: {
      searchText: vi.fn(),
      searchImage: vi.fn(),
      filters: vi.fn(),
    },
  };
});
const { api } = await import("../api/client");
const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

function renderPage() {
  return render(
    <MemoryRouter>
      <SearchProvider>
        <SearchPage />
      </SearchProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocked.filters.mockResolvedValue(filtersResponse);
});

describe("SearchPage", () => {
  it("shows a loading state, then a ranked grid with scores", async () => {
    let resolve!: (v: unknown) => void;
    mocked.searchText.mockReturnValue(new Promise((r) => (resolve = r)));
    renderPage();
    await userEvent.type(screen.getByLabelText(/describe a fashion item/i), "red dress");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(screen.getByRole("status", { name: /loading results/i })).toBeInTheDocument();
    resolve(searchResponse(3));

    const grid = await screen.findByRole("list", { name: /search results/i });
    expect(within(grid).getAllByRole("listitem")).toHaveLength(3);
    expect(within(grid).getByText("0.400")).toBeInTheDocument();
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getAllByAltText(/red short sleeve dress — product photo/i)).toHaveLength(3);
    expect(mocked.searchText).toHaveBeenCalledWith("red dress", {}, expect.objectContaining({ topK: 24 }), expect.anything());
  });

  it("rejects an empty query without calling the API", async () => {
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/describe what you're looking for/i);
    expect(mocked.searchText).not.toHaveBeenCalled();
  });

  it("shows a distinct empty state for zero results", async () => {
    mocked.searchText.mockResolvedValue(searchResponse(0));
    renderPage();
    await userEvent.type(screen.getByLabelText(/describe a fashion item/i), "red dress{enter}");
    expect(await screen.findByTestId("empty-state")).toHaveTextContent(/no matching items found/i);
    expect(screen.queryByTestId("error-state")).not.toBeInTheDocument();
  });

  it("shows an inline error state with retry when the call fails", async () => {
    mocked.searchText.mockRejectedValueOnce(new ApiError("Can't reach the search server.", 0, "network_error"));
    mocked.searchText.mockResolvedValueOnce(searchResponse(2));
    renderPage();
    await userEvent.type(screen.getByLabelText(/describe a fashion item/i), "red dress{enter}");
    const err = await screen.findByTestId("error-state");
    expect(err).toHaveTextContent(/can't reach the search server/i);
    await userEvent.click(within(err).getByRole("button", { name: /try again/i }));
    expect(await screen.findByRole("list", { name: /search results/i })).toBeInTheDocument();
  });

  it("re-runs the search with a filter applied", async () => {
    mocked.searchText.mockResolvedValue(searchResponse(2));
    renderPage();
    await userEvent.type(screen.getByLabelText(/describe a fashion item/i), "red dress{enter}");
    await screen.findByRole("list", { name: /search results/i });
    await userEvent.click(await screen.findByLabelText(/^skirt/i));
    await waitFor(() =>
      expect(mocked.searchText).toHaveBeenLastCalledWith("red dress", { category: ["skirt"] }, expect.anything(), expect.anything()),
    );
  });

  it("validates uploads client-side and searches with a valid image", async () => {
    mocked.searchImage.mockResolvedValue(searchResponse(1, { mode: "image", query: null }));
    renderPage();
    const input = screen.getByTestId("file-input") as HTMLInputElement;

    await userEvent.upload(input, new File(["gif"], "a.gif", { type: "image/gif" }), { applyAccept: false });
    expect(await screen.findByText(/unsupported file type/i)).toBeInTheDocument();
    expect(mocked.searchImage).not.toHaveBeenCalled();

    await userEvent.upload(input, new File(["png"], "a.png", { type: "image/png" }));
    await waitFor(() => expect(mocked.searchImage).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("list", { name: /search results/i })).toBeInTheDocument();
  });

  it("records searches in history", async () => {
    mocked.searchText.mockResolvedValue(searchResponse(1));
    renderPage();
    await userEvent.type(screen.getByLabelText(/describe a fashion item/i), "blue jeans{enter}");
    await screen.findByRole("list", { name: /search results/i });
    expect(screen.getByText("Recent:")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "blue jeans" })).toBeInTheDocument();
  });
});
