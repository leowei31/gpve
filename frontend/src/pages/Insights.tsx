import { useEffect, useState } from "react";
import { getStats, type Stats } from "../lib/api";
import GameCard from "../components/GameCard";
import Spinner from "../components/Spinner";

export default function Insights() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load stats"));
  }, []);

  if (error) return <p className="text-sm text-red-300">{error}</p>;
  if (!stats) return <Spinner />;

  const maxGenre = Math.max(...stats.top_genres.map((g) => g.n), 1);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Catalog Insights</h1>
        <p className="text-sm text-gp-muted">
          {stats.total} games · avg rating {stats.avg_rating ?? "—"} · a 2022 Game Pass snapshot
        </p>
      </div>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="card p-5">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gp-muted">Top genres</h2>
          <div className="space-y-2">
            {stats.top_genres.map((g) => (
              <div key={g.name} className="flex items-center gap-3">
                <span className="w-24 shrink-0 truncate text-sm">{g.name}</span>
                <div className="h-3 flex-1 overflow-hidden rounded-full bg-gp-panel">
                  <div className="h-full rounded-full bg-gp-green" style={{ width: `${(g.n / maxGenre) * 100}%` }} />
                </div>
                <span className="w-8 text-right text-xs tabular-nums text-gp-muted">{g.n}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card p-5">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gp-muted">Common vibe tags</h2>
          <div className="flex flex-wrap gap-2">
            {stats.top_tags.map((t) => (
              <span key={t.name} className="chip" style={{ fontSize: `${0.7 + Math.min(t.n / 120, 0.5)}rem` }}>
                {t.name}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section>
        <h2 className="mb-1 text-lg font-semibold">Hidden gems 💎</h2>
        <p className="mb-4 text-sm text-gp-muted">
          Highly rated, lightly played — the back-catalog worth reigniting.
        </p>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {stats.hidden_gems.map((g) => (
            <GameCard
              key={g.title}
              title={g.title}
              cover_url={g.cover_url}
              genres={g.genres}
              rating={g.rating}
              footer={<p className="mt-1 text-[11px] text-gp-muted">{g.gamers.toLocaleString()} players</p>}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
