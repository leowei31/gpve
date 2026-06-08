import { NavLink, Outlet } from "react-router-dom";

const tabs = [
  { to: "/", label: "Discover", end: true },
  { to: "/collections", label: "Collections" },
  { to: "/insights", label: "Insights" },
];

export default function Layout() {
  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-20 border-b border-gp-line bg-gp-ink/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
          <NavLink to="/" className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-gp-green font-black text-white shadow-glow">
              G
            </span>
            <span className="text-sm font-semibold tracking-wide">
              GamePass <span className="text-gp-glow">Vibe</span>
            </span>
          </NavLink>
          <nav className="flex items-center gap-1">
            {tabs.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                end={t.end}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm transition ${
                    isActive
                      ? "bg-gp-card text-white"
                      : "text-gp-muted hover:text-white"
                  }`
                }
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-5 py-8">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-6xl px-5 pb-10 pt-4 text-center text-xs text-gp-muted">
        Vibes matched against a 2022 Game Pass snapshot · enriched via RAWG · reputation via web search
      </footer>
    </div>
  );
}
