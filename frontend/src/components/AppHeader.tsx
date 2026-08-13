import { Link } from "@/router";

export function AppHeader() {
  return (
    <header className="app-header">
      <Link to="/" className="app-header__brand">
        未来のPRネタを作り出すAI
      </Link>
    </header>
  );
}
