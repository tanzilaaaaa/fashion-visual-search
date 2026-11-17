import { Link } from "react-router-dom";
import { EmptyState } from "../components/States";

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-20">
      <EmptyState title="Page not found">
        <Link to="/" className="font-medium text-accent underline">Go to search</Link>
      </EmptyState>
    </div>
  );
}
