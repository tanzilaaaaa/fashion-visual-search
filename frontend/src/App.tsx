import { Route, Routes } from "react-router-dom";
import { Header } from "./components/Header";
import { RequireAuth } from "./context/AuthContext";
import { AboutPage } from "./pages/AboutPage";
import { ItemPage } from "./pages/ItemPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { SearchPage } from "./pages/SearchPage";

export default function App() {
  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <Header />
      <main id="main">
        <Routes>
          <Route path="/" element={<RequireAuth><SearchPage /></RequireAuth>} />
          <Route path="/item/:id" element={<RequireAuth><ItemPage /></RequireAuth>} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      <footer className="border-t border-stone-200 py-6 text-center text-xs text-ink-muted">
        CLIP ViT-B/32 · FAISS · DeepFashion2 — built for the Polaris School of Technology OJT programme
      </footer>
    </div>
  );
}
