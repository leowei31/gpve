// Typed client for the GPVE backend. Same-origin in prod; Vite proxies /api in dev.

export interface VibeIntent {
  search_query: string;
  genres: string[];
  mood_tags: string[];
  session_length: "short" | "medium" | "long" | "any";
  social: "solo" | "multiplayer" | "any";
}

export interface Source {
  title: string | null;
  url: string | null;
}

export interface Recommendation {
  title: string;
  cover_url: string | null;
  released: string | null;
  genres: string[];
  tags: string[];
  rating: number | null;
  metacritic: number | null;
  vibe_similarity: number;
  metric_score: number;
  web_score: number;
  final_score: number;
  rationale: string | null;
  sources: Source[];
}

export interface VibeResponse {
  vibe: string;
  intent: VibeIntent;
  recommendations: Recommendation[];
}

export interface Game {
  id: number;
  title: string;
  cover_url: string | null;
  genres: string[];
  tags: string[];
  rating: number | null;
  gamers: number | null;
  time_midpoint: number | null;
  released: string | null;
  summary: string | null;
}

// Full single-game profile (GET /api/games/{id}) — the extra metric columns the detail page shows.
export interface GameDetail {
  id: number;
  title: string;
  cover_url: string | null;
  genres: string[];
  tags: string[];
  rating: number | null;
  gamers: number | null;
  completion_pct: number | null;
  time_min_hours: number | null;
  time_max_hours: number | null;
  time_midpoint: number | null;
  released: string | null;
  metacritic: number | null;
  summary: string | null;
  true_achievement: number | null;
  game_score: number | null;
}

// A nearest-neighbour entry (GET /api/games/{id}/similar) — lean shape for the similar-games grid.
export interface SimilarGame {
  id: number;
  title: string;
  cover_url: string | null;
  genres: string[];
  rating: number | null;
  released: string | null;
  similarity: number;
}

export interface Stats {
  total: number;
  avg_rating: number | null;
  top_genres: { name: string; n: number }[];
  top_tags: { name: string; n: number }[];
  hidden_gems: { id: number; title: string; rating: number; gamers: number; cover_url: string | null; genres: string[] }[];
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${detail ? ` — ${detail}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export function recommend(vibe: string): Promise<VibeResponse> {
  return fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vibe }),
  }).then((r) => json<VibeResponse>(r));
}

export function getStats(): Promise<Stats> {
  return fetch("/api/stats").then((r) => json<Stats>(r));
}

export function getGames(params: {
  genre?: string;
  search?: string;
  sort?: "rating" | "popularity" | "recent";
}): Promise<{ total: number; games: Game[] }> {
  const q = new URLSearchParams();
  if (params.genre) q.set("genre", params.genre);
  if (params.search) q.set("search", params.search);
  if (params.sort) q.set("sort", params.sort);
  q.set("limit", "48");
  return fetch(`/api/games?${q}`).then((r) => json<{ total: number; games: Game[] }>(r));
}

export function getGame(id: number | string): Promise<GameDetail> {
  return fetch(`/api/games/${id}`).then((r) => json<GameDetail>(r));
}

export function getSimilar(id: number | string): Promise<{ games: SimilarGame[] }> {
  return fetch(`/api/games/${id}/similar`).then((r) => json<{ games: SimilarGame[] }>(r));
}
