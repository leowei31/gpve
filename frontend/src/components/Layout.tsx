import { NavLink, Outlet, useLocation } from "react-router-dom";

const tabs = [
  { to: "/", label: "Discover", end: true },
  { to: "/collections", label: "Collections" },
  { to: "/insights", label: "Insights" },
];

export default function Layout() {
  const location = useLocation();

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-20 border-b border-gp-line/70 bg-gp-ink/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
          <NavLink to="/" className="group flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-gp-green font-black text-white shadow-soft transition-transform duration-300 group-hover:scale-105">
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
                  `relative rounded-lg px-3 py-1.5 text-sm transition-colors duration-200 ${
                    isActive ? "text-white" : "text-gp-muted hover:text-white"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {/* Active pill — same element across tabs would need shared layout; a simple
                        fade keeps it lightweight and smooth. */}
                    {isActive && (
                      <span className="absolute inset-0 -z-10 animate-scale-in rounded-lg bg-gp-card shadow-soft" />
                    )}
                    {t.label}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      {/* Re-key on route change so each page plays its entrance animation. */}
      <main key={location.pathname} className="mx-auto max-w-6xl animate-fade-up px-5 py-8">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-6xl px-5 pb-10 pt-4 text-center text-xs text-gp-muted">
        Vibes matched against a 2022 Game Pass snapshot · enriched via RAWG · reputation via web search
      </footer>
    </div>
  );
}
