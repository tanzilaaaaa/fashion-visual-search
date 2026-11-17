import { Link } from "react-router-dom";
import { Logo } from "../components/Logo";

export function NotFoundPage() {
  return (
    <div className="relative grid min-h-screen place-items-center px-4">
      <div className="bg-mesh pointer-events-none absolute inset-0" aria-hidden="true" />
      <main id="main" className="relative text-center">
        <div className="flex justify-center"><Logo /></div>
        <p className="mt-10 font-display text-8xl font-semibold text-gradient">404</p>
        <h1 className="mt-2 font-display text-2xl font-semibold text-ink">This page isn't in the catalogue</h1>
        <p className="mt-2 text-ink-soft">The link may be broken, or the page has moved.</p>
        <div className="mt-8 flex justify-center gap-3">
          <Link to="/" className="btn-ghost">Home</Link>
          <Link to="/app" className="btn-primary">Go to search</Link>
        </div>
      </main>
    </div>
  );
}
