import { Outlet } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";
import { RequireAuth } from "../context/AuthContext";
import { SearchProvider } from "../context/SearchContext";

export function AppLayout() {
  return (
    <RequireAuth>
      <SearchProvider>
        <div className="relative min-h-screen">
          <div className="bg-mesh pointer-events-none absolute inset-x-0 top-0 h-[28rem]" aria-hidden="true" />
          <AppHeader />
          <main id="main" className="relative">
            <Outlet />
          </main>
          <footer className="relative border-t border-line py-8 text-center text-xs text-ink-muted">
            Lookbook · CLIP ViT-B/32 + fine-tuned adapter · FAISS · DeepFashion2 — Polaris School of Technology OJT
          </footer>
        </div>
      </SearchProvider>
    </RequireAuth>
  );
}
