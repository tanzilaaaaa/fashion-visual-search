import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { AboutPage } from "./pages/AboutPage";
import { AuthPage } from "./pages/AuthPage";
import { ItemPage } from "./pages/ItemPage";
import { LandingPage } from "./pages/LandingPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { SearchPage } from "./pages/SearchPage";

export default function App() {
  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2 focus:text-ink focus:shadow-lift"
      >
        Skip to content
      </a>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/signin" element={<AuthPage mode="signin" />} />
        <Route path="/signup" element={<AuthPage mode="signup" />} />
        <Route path="/login" element={<Navigate to="/signin" replace />} />
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<SearchPage />} />
          <Route path="item/:id" element={<ItemPage />} />
          <Route path="insights" element={<AboutPage />} />
        </Route>
        <Route path="/item/:id" element={<LegacyItemRedirect />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </>
  );
}

function LegacyItemRedirect() {
  const id = window.location.pathname.split("/").pop() ?? "";
  return <Navigate to={`/app/item/${id}${window.location.hash}`} replace />;
}
