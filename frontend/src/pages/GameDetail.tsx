import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getGame, getSimilar, type GameDetail as Game, type SimilarGame } from "../lib/api";
import CoverImage from "../components/CoverImage";
import GameCard from "../components/GameCard";
import Spinner from "../components/Spinner";

function fmtHours(n: number): string {
  return Number.isInteger(n) ? `${n}` : n.toFixed(1);
}

// Prefer a real range; fall back to the midpoint, then to an open lower bound. Null = unknown.
function playtime(g: Game): string | null {
  const { time_min_hours: lo, time_max_hours: hi, time_midpoint: mid } = g;
  if (lo != null && hi != null && hi !== lo) return `${fmtHours(lo)}–${fmtHours(hi)} hrs`;
  if (mid != null) return `~${fmtHours(mid)} hrs`;
  if (lo != null) return `${fmtHours(lo)}+ hrs`;
  return null;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-3">
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-gp-muted">{label}</div>
    </div>
  );
}

export default function GameDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [game, setGame] = useState<Game | null>(null);
  const [similar, setSimilar] = useState<SimilarGame[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setGame(null);
    setError(null);
    // Profile is required; similar is best-effort (never blocks or fails the page).
    getGame(id)
      .then(setGame)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load game"));
    getSimilar(id)
      .then((r) => setSimilar(r.games))
      .catch(() => setSimilar([]));
  }, [id]);

  if (error)
    return (
      <div className="space-y-4 py-16 text-center">
        <p className="text-sm text-gp-muted">Couldn't load that game.</p>
        <button onClick={() => navigate("/collections")} className="chip">
          ← Back to Collections
        </button>
      </div>
    );

  if (!game) return <Spinner />;

  const stats: { label: string; value: string }[] = [];
  if (game.rating != null) stats.push({ label: "Rating", value: `★ ${game.rating.toFixed(1)}` });
  if (game.gamers != null) stats.push({ label: "Players", value: game.gamers.toLocaleString() });
  const time = playtime(game);
  if (time) stats.push({ label: "Avg playtime", value: time });
  if (game.completion_pct != null) stats.push({ label: "Completion", value: `${Math.round(game.completion_pct)}%` });
  if (game.metacritic != null) stats.push({ label: "Metacritic", value: `${game.metacritic}` });
  if (game.game_score != null) stats.push({ label: "Gamerscore", value: game.game_score.toLocaleString() });
  if (game.true_achievement != null)
    stats.push({ label: "TrueAchievement", value: game.true_achievement.toLocaleString() });

  return (
    <div className="space-y-10">
      <button onClick={() => navigate(-1)} className="text-sm text-gp-muted transition-colors hover:text-gp-glow">
        ← Back
      </button>

      <section className="grid gap-6 md:grid-cols-[260px_1fr]">
        <div className="card aspect-[16/10] overflow-hidden md:aspect-[3/4]">
          <CoverImage src={game.cover_url} alt={game.title} />
        </div>
        <div className="space-y-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{game.title}</h1>
            <p className="mt-1 text-sm text-gp-muted">
              {[game.released?.slice(0, 4), game.genres.slice(0, 3).join(" · ")].filter(Boolean).join(" · ") || "—"}
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {game.genres.map((g) => (
              <span key={g} className="chip">{g}</span>
            ))}
            {game.tags.slice(0, 8).map((t) => (
              <span key={t} className="chip opacity-70">{t}</span>
            ))}
          </div>
          {game.summary && <p className="max-w-2xl text-sm leading-relaxed text-gray-300">{game.summary}</p>}
        </div>
      </section>

      {stats.length > 0 && (
        <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {stats.map((s) => (
            <Stat key={s.label} label={s.label} value={s.value} />
          ))}
        </section>
      )}

      {similar.length > 0 && (
        <section>
          <h2 className="mb-1 text-lg font-semibold">Similar games</h2>
          <p className="mb-4 text-sm text-gp-muted">Nearest matches by vibe — pure vector similarity, no LLM.</p>
          <div className="stagger grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {similar.map((s) => (
              <GameCard
                key={s.id}
                id={s.id}
                title={s.title}
                cover_url={s.cover_url}
                genres={s.genres}
                rating={s.rating}
                footer={<p className="mt-1 text-[11px] text-gp-muted">{Math.round(s.similarity * 100)}% match</p>}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
