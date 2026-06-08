import { useState } from "react";
import { recommend, type Recommendation, type VibeResponse } from "../lib/api";
import CoverImage from "../components/CoverImage";
import Spinner from "../components/Spinner";

const SUGGESTIONS = [
  "something eerie and atmospheric to play alone late at night",
  "a cozy wholesome game to relax and de-stress",
  "fast brutal competitive shooter with friends",
  "a deep epic fantasy RPG to sink 100 hours into",
  "a short clever puzzle game for a quick break",
];

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-12 shrink-0 text-[10px] uppercase tracking-wide text-gp-muted">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-gp-panel">
        <div className="h-full rounded-full bg-gp-glow/80" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="w-8 shrink-0 text-right text-[10px] tabular-nums text-gp-muted">
        {value.toFixed(2)}
      </span>
    </div>
  );
}

function ResultCard({ rec, rank }: { rec: Recommendation; rank: number }) {
  return (
    <article className="card flex flex-col overflow-hidden sm:flex-row">
      <div className="relative aspect-[16/10] w-full shrink-0 sm:aspect-auto sm:w-56">
        <CoverImage src={rec.cover_url} alt={rec.title} />
        <span className="absolute left-2 top-2 grid h-6 w-6 place-items-center rounded-full bg-gp-green text-xs font-bold text-white shadow-glow">
          {rank}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <h3 className="text-lg font-semibold">{rec.title}</h3>
          <span className="text-xs text-gp-muted">
            {rec.released?.slice(0, 4) ?? ""} {rec.rating != null && `· ★ ${rec.rating.toFixed(1)}`}
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {rec.genres.slice(0, 3).map((g) => (
            <span key={g} className="chip">{g}</span>
          ))}
          {rec.tags.slice(0, 3).map((t) => (
            <span key={t} className="chip opacity-70">{t}</span>
          ))}
        </div>
        {rec.rationale && <p className="text-sm leading-relaxed text-gray-300">{rec.rationale}</p>}
        <div className="mt-auto grid gap-1 pt-1">
          <ScoreBar label="vibe" value={rec.vibe_similarity} />
          <ScoreBar label="metrics" value={rec.metric_score} />
          <ScoreBar label="web" value={rec.web_score} />
        </div>
        {rec.sources.length > 0 && (
          <div className="flex flex-wrap gap-x-3 gap-y-1 pt-1 text-[11px] text-gp-muted">
            <span>sources:</span>
            {rec.sources.slice(0, 3).map(
              (s, i) =>
                s.url && (
                  <a key={i} href={s.url} target="_blank" rel="noreferrer" className="truncate hover:text-gp-glow">
                    {s.title?.slice(0, 36) || s.url}
                  </a>
                )
            )}
          </div>
        )}
      </div>
    </article>
  );
}

export default function Discover() {
  const [vibe, setVibe] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VibeResponse | null>(null);

  async function submit(text: string) {
    const v = text.trim();
    if (!v || loading) return;
    setVibe(v);
    setLoading(true);
    setError(null);
    try {
      setResult(await recommend(v));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="space-y-4 pt-4 text-center">
        <h1 className="text-3xl font-bold sm:text-4xl">
          What's your <span className="text-gp-glow">vibe</span>?
        </h1>
        <p className="mx-auto max-w-xl text-sm text-gp-muted">
          Describe a feeling, a mood, an occasion — get 5 older Game Pass titles matched to it,
          blending your vibe, the catalog's 2022 stats, and live web reputation.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit(vibe);
          }}
          className="mx-auto flex max-w-2xl flex-col gap-2 sm:flex-row"
        >
          <input
            value={vibe}
            onChange={(e) => setVibe(e.target.value)}
            placeholder="e.g. something eerie and atmospheric to play alone late at night"
            className="flex-1 rounded-xl border border-gp-line bg-gp-panel/70 px-4 py-3 text-sm outline-none transition focus:border-gp-glow/60 focus:shadow-glow"
          />
          <button
            type="submit"
            disabled={loading || !vibe.trim()}
            className="rounded-xl bg-gp-green px-5 py-3 text-sm font-semibold text-white transition hover:brightness-110 disabled:opacity-40"
          >
            {loading ? "Matching…" : "Find my games"}
          </button>
        </form>
        <div className="flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => submit(s)} disabled={loading} className="chip">
              {s}
            </button>
          ))}
        </div>
      </section>

      {error && (
        <div className="mx-auto max-w-2xl rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading && <Spinner label="Reading the vibe, searching the catalog & the web…" />}

      {!loading && result && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-gp-muted">
            <span>interpreted as</span>
            {result.intent.mood_tags.map((m) => (
              <span key={m} className="chip">{m}</span>
            ))}
            <span className="chip">session: {result.intent.session_length}</span>
            <span className="chip">play: {result.intent.social}</span>
          </div>
          <div className="grid gap-4">
            {result.recommendations.map((rec, i) => (
              <ResultCard key={rec.title} rec={rec} rank={i + 1} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
