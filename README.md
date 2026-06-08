# GPVE — Xbox Game Pass Vibe Discovery Engine

Free-form *vibe* in → **5 older Game Pass titles** out, each with cover art and a per-game
rationale, ranked by blending the user's vibe, the 2022 catalog metrics, and live web
reputation. Companion docs: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) (what/how)
and [docs/DESIGN_RATIONALE.md](docs/DESIGN_RATIONALE.md) (why).

> **Status: complete and deployed.** CSV cleaning + tests · EDA notebook · RAWG enrichment
> (446/446) · embeddings (446 × 768-dim) · Postgres/pgvector · 6-stage request pipeline +
> FastAPI · React/Vite/Tailwind SPA (Discover · Collections · Insights) · README deliverables
> (architecture + scaling, determinism, AI log) · single-container Dockerfile · **Terraform IaC
> deployed end-to-end on GCP with GitHub → Cloud Build CI/CD** ([infra/](infra/)). 80 backend
> tests green. The ranking design is grounded in [notebooks/eda.ipynb](notebooks/eda.ipynb).

## Requirements coverage (REQ-001–009)

Every requirement from the brief, mapped to where it's satisfied in the as-built code:

| REQ | Requirement | As-built location |
|---|---|---|
| 001 | Parse + sanitize the dirty 2022 CSV (no crashes, no silent imputation) | [clean.py](backend/ingest/clean.py) · [test_clean.py](backend/tests/test_clean.py) |
| 002 | Prominent free-form vibe input | [Discover.tsx](frontend/src/pages/Discover.tsx) → `POST /api/recommend` |
| 003 | Parse vibe → structured intent + candidate matches | [parse.py](backend/app/pipeline/parse.py) + [retrieve.py](backend/app/pipeline/retrieve.py) |
| 004 | Live web search for deeper, current context | [reputation.py](backend/app/pipeline/reputation.py) (Tavily) |
| 005 | Dynamic cover-art URL resolution | [enrich.py](backend/ingest/enrich.py) (RAWG, 446/446) |
| 006 | Synthesize 3 inputs (vibe + metrics + web) into a ranking | [metric.py](backend/app/pipeline/metric.py) + [rank.py](backend/app/pipeline/rank.py) |
| 007 | Return exactly 5 titles | [rank.py](backend/app/pipeline/rank.py) (`top_k=5`) |
| 008 | Render cover art, with a fallback for missing art | [CoverImage.tsx](frontend/src/components/CoverImage.tsx) · [GameCard.tsx](frontend/src/components/GameCard.tsx) |
| 009 | Per-game vibe rationale | [rationale.py](backend/app/pipeline/rationale.py) (grounded) |

## Layout

```
data/        Gamepass_Games_v1.csv (source) + generated caches
backend/
  sql/       01_schema.sql, 02_match_games.sql  (auto-run on first DB boot)
  ingest/    clean · enrich · embed · load · seed  (offline pipeline)
  app/
    clients/   gemini · tavily · db · cache  (external services)
    pipeline/  parse → retrieve → metric → reputation → rank → rationale → recommend
    routers/   recommend.py · catalog.py
    main.py    FastAPI app (serves API + compiled SPA)
  tests/     80 tests (clean / enrich / embed / load / metric / reputation)
frontend/    React + Vite + Tailwind SPA (Discover · Collections · Insights)
Dockerfile · docker-compose.yml · cloudbuild.yaml   build + local DB + CI
infra/       Terraform — full GCP deploy (Cloud Run · Cloud SQL+pgvector · Memorystore · …)
docs/        plan + rationale
```

## Run locally

### What you need on a fresh machine (besides cloning)

**Tools**

| Tool | For | Notes |
|---|---|---|
| **Python 3.12** | backend + ingestion | |
| **Docker + Docker Compose** | local Postgres 16 + `pgvector` | or bring your own Postgres 16 with the `vector` extension |
| **Node.js 20 + npm** | the frontend dev server / build | optional — the Docker image builds the SPA for you |

**API keys** — copy `backend/.env.example` → `backend/.env` and fill in:

| Key | Needed for | Required? |
|---|---|---|
| `GEMINI_API_KEY` | every recommend (vibe parse, query embedding, rationale) | **Yes, to use the app.** Needs free-tier/credits on the project or it 429s. [Get one](https://aistudio.google.com/apikey) |
| `TAVILY_API_KEY` | live web reputation (Stage 4) | **Recommended.** Degrades gracefully + is cached, but fresh games need it. [Get one](https://app.tavily.com) |
| `RAWG_API_KEY` | re-running enrichment (`ingest.enrich`) only | **Optional** — see below. [Get one](https://rawg.io/apidocs) |

**No dataset download needed.** The CSV *and* the enrichment / embeddings / web-reputation caches
are committed, so you can build the catalog with **zero API calls** — `RAWG_API_KEY` is only
needed if you want to *re-enrich* from scratch. `DATABASE_URL` is pre-filled for the
docker-compose Postgres; leave `REDIS_URL` blank to use the local JSON-file cache.

### Install + run

```bash
# 1. Backend deps (virtualenv recommended)
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q                                 # 80 tests — sanity check

# 2. Database: Postgres 16 + pgvector (schema auto-applied on first boot)
docker compose up -d --wait

# 3. Load the 446-game catalog from the committed caches (no API keys, no RAWG/Gemini calls)
python -m ingest.load

# 4. Serve the API (and the SPA build, if present)
python -m uvicorn app.main:app --port 8000          # /api/health · /api/stats · POST /api/recommend
```

> **Rebuilding the catalog from scratch** (instead of the committed caches) is optional and needs
> the keys: `ingest.clean` → `ingest.enrich` (RAWG) → `ingest.embed` (Gemini) → `ingest.load`.
> Each step is cached/incremental (`--force` refreshes; `embed --dry-run` previews text with no
> API calls).

### Frontend (React + Vite + Tailwind)

```bash
cd frontend
npm install
npm run dev      # :5173, proxies /api → :8000  (run uvicorn alongside)
npm run build    # → frontend/dist, which uvicorn serves at http://localhost:8000
```

Three pages: **Discover** (the prominent vibe box → 5 ranked cards with cover art, rationale,
and the vibe/metric/web score breakdown), **Collections** (browse/filter the catalog), and
**Insights** (catalog analytics + hidden gems). Missing/dead cover URLs fall back to a
generated tile (REQ-008).

### As one container (Cloud Run-ready)

The [Dockerfile](Dockerfile) is multi-stage: it builds the SPA, then serves it **and** the API
from FastAPI in a single image listening on `$PORT` (default 8080). DB + keys are supplied at
runtime; the catalog must already be ingested into that DB.

```bash
docker build -t gpve:latest .
docker run -p 8080:8080 --env-file backend/.env gpve:latest   # DATABASE_URL must reach Postgres
```

### Deploy to GCP (Terraform + CI/CD)

[infra/](infra/) provisions the whole production target as code and has been **deployed
end-to-end**: Cloud Run (the container above) + a Cloud Run **Job** that seeds/re-loads the
catalog, Cloud SQL (Postgres 16 + `pgvector`), Memorystore (Redis), Artifact Registry, Secret
Manager, and a private VPC. The reputation cache transparently uses Memorystore when `REDIS_URL`
is set and the local JSON file otherwise ([app/clients/cache.py](backend/app/clients/cache.py)),
so dev and prod share one code path.

**CI/CD:** a push to `main` triggers Cloud Build (via a 2nd-gen GitHub connection) to build →
push → deploy a new Cloud Run revision — [cloudbuild.yaml](cloudbuild.yaml) +
[infra/cicd.tf](infra/cicd.tf). See [infra/README.md](infra/README.md) for prerequisites (gcloud,
Terraform, a billing-enabled GCP project), the apply order, the one-time seed, CI setup, cost
(~$50–60/mo if left running), and teardown. *(The brief asks only
for a local app + a written scaling proposal; the live deploy + CI/CD are beyond-scope — the
proposal made runnable.)*

**Verified end-to-end:** `POST /api/recommend` turns *"something eerie and atmospheric to play
alone late at night"* into LIMBO, Carrion, Alien: Isolation, … each with a grounded "why it
fits" rationale.

## Recommendation pipeline (REQ-002–009)

`POST /api/recommend {"vibe": "..."}` runs six stages; the LLM only handles *language*, all
ranking is deterministic arithmetic in code (ADR-9):

| # | Stage | What | LLM? |
|---|---|---|---|
| 1 | parse | vibe → structured intent (genres, mood, session, social) | Gemini (temp 0, JSON) |
| 2 | retrieve | embed query → top-25 by pgvector cosine | embedding only |
| 3 | metric | re-score on quality / popularity / session / social (EDA-grounded) | no — pure |
| 4 | reputation | live Tavily on the leaders, cached by title, lexicon sentiment | no — pure synth |
| 5 | rank | `0.5·vibe + 0.3·metric + 0.2·web` → top 5 | no — pure |
| 6 | rationale | grounded per-game "why it fits", from the same evidence | Gemini (temp 0, JSON) |

Transient Gemini 5xx/rate errors are retried with backoff; web reputation and rationale degrade
gracefully (a recommendation is never sunk by an enhancer failing).

## Enrichment (REQ-005)

The 2022 CSV has **no semantic columns** (EDA §2), so each cleaned title is matched to RAWG for
genres, tags, a description, and an official cover image. Match confidence is a principled
blend — `max(Jaccard, forward-containment)` over diacritic-folded, stopword-stripped tokens,
with a Jaccard tie-break — not a magic threshold:

| | Result |
|---|---|
| Matched | **446 / 446** (every title; verified, not just "found") |
| Sub-1.0 scores | legitimate variants (`Dragon Age II`→`Dragon Age 2`, `GRID`→`GRID (2019)`) |
| Hard tail | `DOOM (1993)` (year-stripped search), `Backbone`→`Tails Noir` (documented rename override) |
| No cover art | 2 titles (`Killer Instinct Classic` ×2) → UI placeholder; never fabricated |

Re-runs are incremental (cached titles skipped, misses retried); `--force` refreshes all.

## What the cleaner handles (REQ-001)

`455 rows → 446 unique games`, dirty data normalized natively:

| Issue | Example | Handling |
|---|---|---|
| Thousands separators | `"84,143"` | → `84143` (int) |
| Non-numeric ratio | `-` (Shadowrun rows) | → `null` (no crash) |
| Playtime ranges/open/decimal | `1000+ hours`, `0.5-1 hour` | → `(min, max, midpoint)`, open bound = null max |
| Relative date | `Yesterday` (Loot River) | → `null` |
| Missing playtime / rating | 34 / 3 rows | kept `null`, **never imputed** |
| Duplicates + platform variants | `FIFA 21 (Xbox One)` | collapsed by normalized title (keep richest) |

---

# Deliverable: System Architecture

Full ADR-style reasoning (and rejected alternatives) lives in
[docs/DESIGN_RATIONALE.md](docs/DESIGN_RATIONALE.md); this is the **as-built** summary.

```
                          ┌─────────────────────────────────────────────┐
  Browser ── HTTP ──▶     │  FastAPI (app/main.py)  — one container      │
  React SPA (Vite)        │   /            → serves the built SPA        │
  Discover/Collections/   │   /api/recommend, /api/stats, /api/games     │
  Insights                │   pipeline/  parse→retrieve→metric→          │
                          │              reputation→rank→rationale       │
                          └───┬───────────────┬──────────────┬──────────┘
                     asyncpg  │        Gemini │       Tavily │  (wrapped,
                              ▼               ▼              ▼   retried, threaded)
                   ┌────────────────┐  ┌────────────┐  ┌────────────┐
                   │ Postgres +     │  │ Gemini API │  │ Tavily API │
                   │ pgvector       │  │ embed+gen  │  │ web search │
                   │ (446 games,    │  └────────────┘  └────────────┘
                   │  768-dim vecs) │
                   └────────────────┘
```

**Two halves.** (1) An **offline ingestion pipeline** (`ingest/`) — cached, idempotent — turns
the dirty CSV into a queryable semantic catalog: `clean` → `enrich` (RAWG
genres/tags/summary/cover) → `embed` (Gemini 768-dim) → `load` (Postgres). (2) A **runtime
request pipeline** (`app/pipeline/`) — the six stages above, deterministic ranking in code, LLM
for language only. One container serves both the API and the compiled SPA.

**As-built stack.** React + Vite + Tailwind · FastAPI + asyncpg · Postgres 16 + `pgvector` ·
Gemini `gemini-embedding-001` (768-dim) + `gemini-2.5-flash` · RAWG (enrichment + cover art) ·
Tavily (web reputation). Deltas from the design baseline: Gemini model names updated (the
originally-specified `text-embedding-004`/`gemini-1.5-flash` were retired); UI uses hand-rolled
Tailwind components rather than the shadcn/ui CLI; web reputation is synthesized by a
deterministic lexicon rather than an LLM.

## Scaling from a 2022 CSV to a live, telemetry-driven system

The single static input (`Gamepass_Games_v1.csv`) stands in for what production would stream.
Because the architecture already separates **ingestion** from **serving**, scaling mostly means
swapping the ingestion source and metric provenance — the request pipeline barely changes.

1. **Catalog freshness.** Replace the CSV with a scheduled reconciliation against the live Game
   Pass catalog; new titles flow through the *same* `enrich → embed → load` steps, departed
   titles drop out of retrieval. (The 2022 snapshot is deliberately frozen here.)
2. **Metrics from real telemetry.** The 2022 columns become **live aggregates** from
   player-event streams (plays, completions, session lengths, churn, ratings) via **Pub/Sub →
   Dataflow/BigQuery → materialized features**. `metric.py`'s signal functions are unchanged;
   only their inputs get fresher and richer.
3. **Embeddings & vector scale.** Re-embed on enrichment change. `pgvector` is trivial at ~450
   rows; the upgrade path is AlloyDB (ScaNN) → Vertex AI Vector Search as the catalog grows.
4. **Web reputation at volume.** Move from per-request Tavily to a scheduled batch refresh into
   a durable cache, or Vertex AI grounding — the title-keyed TTL cache already models this.
   *(Implemented: `REDIS_URL` switches the cache to the Memorystore that [infra/](infra/)
   provisions.)*
5. **Personalization.** Telemetry unlocks per-user signals for a hybrid layer that nudges the
   deterministic score — without surrendering explainability.
6. **Serving & ops.** Cloud Run autoscale; Memorystore for result/web caches; Cloud SQL read
   replicas; observe **latency, cache-hit rate, token spend, fallback rate**; tune ranking
   weights against a labeled eval set, not by hand.

---

# Deliverable: Prompt Engineering & Determinism

**Principle: the LLM handles language; code handles ranking.** Gemini is used in exactly two
places (parse, rationale) and for embeddings — never to order or select games. Every LLM call
runs at **temperature 0 with thinking disabled**, returns **schema-validated JSON** (Pydantic),
and is grounded in data we pass in.

### Determinism & anti-hallucination mechanisms

| Mechanism | Where | Effect |
|---|---|---|
| Ranking is pure arithmetic | `pipeline/rank.py`, `metric.py` | reproducible, tunable, explainable order |
| temp 0 + `thinking_budget=0` | `clients/gemini.py` | stable, low-variance generations |
| Structured output (JSON schema) | parse + rationale | shape-validated; no prose where data is expected |
| Model never sees the catalog | rationale prompt | can only describe the 5 games passed in — can't invent titles |
| Grounded rationale | `pipeline/rationale.py` | claims must come from the given genres/tags/summary + web snippets |
| Deterministic web score | `pipeline/reputation.py` | fixed lexicon over fetched text — same text ⇒ same score (no LLM) |
| Title-keyed web cache (TTL) | `pipeline/reputation.py` | repeat vibes reproducible; fewer live calls |
| Normalized embeddings | `ingest/embed.py` | same text ⇒ same 768-dim unit vector |
| Graceful degradation + retry | `clients/gemini.py` | transient 5xx/429 retried; an enhancer failing never sinks a result |

### Exact prompts (verbatim)

**Stage 1 — vibe parser** (`app/pipeline/parse.py`), returns the `VibeIntent` schema
(`search_query`, `genres[]`, `mood_tags[]`, `session_length`, `social`):

```text
You convert a player's free-form "vibe" into structured search intent for a video-game
recommender. Respond ONLY via the provided schema.

Guidelines:
- Infer only what the vibe implies. Never invent or name specific game titles.
- search_query: a concise phrase (<= 15 words) blending genre + mood for semantic matching.
- genres: plausible genres (e.g. RPG, Shooter, Puzzle, Racing, Platformer). Empty if unclear.
- mood_tags: atmosphere/feel words (e.g. atmospheric, cozy, intense, story-rich, relaxing).
- session_length: "short" for quick/after-work/casual, "long" for epic/deep/grindy, "medium",
  or "any" if the vibe says nothing about length.
- social: "solo" for single-player/alone, "multiplayer" for with-friends/competitive/co-op,
  or "any" if unstated.
- Be deterministic and literal — do not embellish.

Vibe: "{vibe}"
```

**Stage 6 — grounded rationale** (`app/pipeline/rationale.py`), returns one
`{title, rationale}` per game from a single call:

```text
A player described the vibe they're after:
"{vibe}"

For each game below, write 1–2 sentences explaining why it fits that vibe. Ground every claim
in the provided genres, tags, summary, and web reputation — do NOT invent facts, review scores,
or details not present, and do NOT mention any game not in the list. Speak to the player
directly and naturally. Return one entry per game, echoing its exact title.

Games (JSON):
{games}
```

Embedding task types are asymmetric per Gemini guidance: the catalog is embedded with
`RETRIEVAL_DOCUMENT`, the live vibe with `RETRIEVAL_QUERY`.

---

# Deliverable: AI Collaboration Log

Led by the project owner as **senior engineer and product manager**; **Claude Code** was an AI
implementation partner working under that direction. Who did what:

| Area | Owner — senior engineer / PM | Claude Code — implementation partner |
|---|---|---|
| **Architecture & ADRs** | Owned every decision in [DESIGN_RATIONALE.md](docs/DESIGN_RATIONALE.md) — pgvector over Supabase, deterministic ranking over an LLM re-ranker, single-container packaging, GCP-everything; set the *"LLM for language, code for ranking"* constraint | Pressure-tested alternatives on request; wrote the decisions up |
| **Methodology** | Required EDA-first — profile the data *before* designing; used the result to pull completion from the quality term | Ran the EDA notebook; surfaced `completion_pct` ≈ uncorrelated with rating (r≈−0.02) |
| **Scope & product** | Full ambitious build, 3-page priority, determinism trade-off (live Tavily + cache), descoped Game detail / Similar to protect the core | Built to those calls |
| **Code** | Reviewed every change before accepting — pipeline logic, scoring, SQL; verified against live data, never trusted blind | Wrote the pipeline / UI / test code (80 tests) |
| **Data quality** | Challenged the claimed "100% RAWG match"; directed the matcher hardening | Caught the wrong matches (`DOOM (1993)`→2016 reboot, `Backbone`→demo); implemented the fixes |
| **External APIs** | Set the fail-fast-vs-retry policy; provided the live keys/credits | `google-generativeai`→`google-genai` migration; 429 handling |
| **Deployment & CI/CD** | Owned the GCP/CI-CD direction; ran every Terraform/gcloud command; worked the failure cascade to a live system | Wrote the Terraform/config; diagnosed errors (Cloud SQL edition, VPC scaling, seed ordering, 1st→2nd-gen Cloud Build) |
