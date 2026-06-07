-- GPVE catalog schema: cleaned CSV metrics + RAWG enrichment + embeddings, in one store.
-- See DESIGN_RATIONALE.md ADR-1 for why a single Postgres+pgvector store.
create extension if not exists vector;

create table if not exists games (
  id                bigserial primary key,
  title             text not null,
  normalized_title  text,                     -- dedup / enrichment-match key
  -- cleaned catalog metrics (from Gamepass_Games_v1.csv)
  ratio             numeric,                  -- achievement difficulty; null = unknown ("-")
  gamers            integer,                  -- active player count; 0 is a real value
  completion_pct    numeric,
  time_min_hours    numeric,
  time_max_hours    numeric,                  -- null = open upper bound ("1000+") or unknown
  time_midpoint     numeric,                  -- null = unknown length
  rating            numeric,                  -- 2.0-4.8, null allowed
  added_date        date,                     -- null allowed (blank or "Yesterday")
  true_achievement  integer,
  game_score        integer,
  -- enrichment (RAWG / IGDB)
  rawg_id           integer,
  genres            text[],
  tags              text[],
  themes            text[],
  summary           text,
  cover_url         text,
  released          date,
  metacritic        integer,
  -- semantic
  enriched_text     text,
  embedding         vector(768),              -- gemini-embedding-001 @ 768-dim (MRL truncation)
  -- bookkeeping
  enrichment_status text default 'pending',   -- pending | ok | miss
  source_titles     text[],                   -- raw titles merged into this row on dedup
  updated_at        timestamptz default now()
);

-- Optional at ~450 rows (sequential scan is instant); present for the documented scale path.
create index if not exists games_embedding_hnsw
  on games using hnsw (embedding vector_cosine_ops);

create index if not exists games_normalized_title_idx on games (normalized_title);
