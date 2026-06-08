import { useEffect, useState } from "react";
import { getGames, getStats, type Game } from "../lib/api";
import GameCard from "../components/GameCard";
import Spinner from "../components/Spinner";

type Sort = "rating" | "popularity" | "recent";

export default function Collections() {
  const [genres, setGenres] = useState<string[]>([]);
  const [genre, setGenre] = useState<string | undefined>();
  const [sort, setSort] = useState<Sort>("rating");
  const [search, setSearch] = useState("");
  const [games, setGames] = useState<Game[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStats().then((s) => setGenres(s.top_genres.map((g) => g.name))).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const id = setTimeout(() => {
      getGames({ genre, sort, search: search.trim() || undefined })
        .then((r) => {
          setGames(r.games);
          setTotal(r.total);
        })
        .finally(() => setLoading(false));
    }, 250); // debounce search typing
    return () => clearTimeout(id);
  }, [genre, sort, search]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Collections</h1>
          <p className="text-sm text-gp-muted">{total} games · browse the enriched catalog</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search titles…"
            className="field py-1.5"
          />
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as Sort)}
            className="field cursor-pointer py-1.5"
          >
            <option value="rating">Top rated</option>
            <option value="popularity">Most played</option>
            <option value="recent">Newest</option>
          </select>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button onClick={() => setGenre(undefined)} className={`chip ${!genre ? "border-gp-glow/60 text-white" : ""}`}>
          All
        </button>
        {genres.map((g) => (
          <button
            key={g}
            onClick={() => setGenre(g)}
            className={`chip ${genre === g ? "border-gp-glow/60 text-white" : ""}`}
          >
            {g}
          </button>
        ))}
      </div>

      {loading ? (
        <Spinner />
      ) : games.length === 0 ? (
        <p className="py-16 text-center text-sm text-gp-muted">No games match those filters.</p>
      ) : (
        <div
          key={`${genre}-${sort}-${total}`}
          className="stagger grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
        >
          {games.map((g) => (
            <GameCard key={g.id} id={g.id} title={g.title} cover_url={g.cover_url} genres={g.genres} rating={g.rating} />
          ))}
        </div>
      )}
    </div>
  );
}
