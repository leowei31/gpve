# GPVE — Design Rationale & Architecture Decisions

**Project:** Xbox Game Pass Vibe Discovery Engine (GPVE)
**Purpose:** The reasoning behind every architectural and product choice — alternatives rejected and why. The "why" companion to `IMPLEMENTATION_PLAN.md` (the "what/how").
**Status:** MVP built and deployed to GCP with CI/CD. ADRs below record the original decisions; **As-built** notes flag where reality differs.

---

## 1. The problem, restated

Game Pass has hundreds of titles, and older ones with great historical reviews get buried under
new releases. Category filters ("Action", "RPG") can't express the *subjective, situational
mood* a player wants — "an eerie, isolated sci-fi game to explore slowly after work". The goal:
an engine that takes a **free-form vibe**, cross-references the **2022 catalog**, verifies each
candidate's **modern web reputation**, and returns a **polished screen of exactly five older
titles** with cover art and per-game rationale, in a small **multi-page** app.

---

## 2. The single most important finding (this shaped everything)

Before choosing any technology, we profiled the actual dataset (`Gamepass_Games_v1.csv`). The result reframes the entire project:

| Property | Finding |
|---|---|
| Rows | 455 games |
| Columns | 9 |
| Columns present | `GAME`, `RATIO`, `GAMERS`, `COMP %`, `TIME`, `RATING`, `ADDED`, `True_Achievement`, `Game_Score` |
| Semantic columns (genre / theme / mood / description / tags) | **None** |
| `TIME` quality | Dirty: ranges (`100-120 hours`), open bounds (`1000+ hours`), singular (`0.5-1 hour`), **34 nulls** |
| `GAMERS` quality | Strings with thousands separators (`"84,143"`), some bare (`777`) |
| `RATING` | Float 2.0–4.8, **3 nulls** |
| `ADDED` | Date strings (`06 Jan 22`), **1 null** |
| Duplicate titles | 2 |

**The decisive insight:** the dataset is *entirely quantitative* — achievement difficulty, player counts, completion rates, ratings. **Nothing in it describes what a game *is*.** You cannot match "eerie, isolated sci-fi exploration" against a column of achievement ratios. The signal the product depends on **is not in the data**.

### Consequence

The real architecture is not "parse vibe → query the CSV". It is:

> **"parse vibe → query a *semantically enriched* version of the catalog that we build at ingestion time."**

This is the crux of the whole build, and it is the thing most naive attempts get wrong — they wire an LLM directly to the raw columns and produce nonsense, because the columns cannot carry a vibe. Every downstream decision (enrichment source, embeddings, retrieval strategy) follows from solving this **enrichment gap**.

A second, elegant consequence: the enrichment step also solves the **cover-art requirement** (REQ-005) — a games-metadata API returns genres, tags, summary, *and* a cover image in a single call — **and** it gives the rest of the application (detail pages, browse filters, collections, insights, similar-games) something rich to work with. One batch pass over 455 games unlocks everything.

---

## 3. Core architectural principles

Four principles fall out of the finding above and govern the rest of the design:

1. **Enrich at ingestion, match against the enriched catalog.** Build a semantic layer (genres, tags, themes, summary) once, offline, and embed it. The vibe is matched against *that*, not the raw metrics.
2. **Use the LLM for language, use code for ranking.** The model is excellent at turning fuzzy text into structured intent and at writing rationale. It is *not* where the final relevance ordering should live — that belongs in deterministic, debuggable code. This directly serves the brief's "deterministic behavior / prevent hallucinations" requirement.
3. **Reuse the catalog you already build.** Once the enriched catalog + embeddings + pipeline exist, additional product surface is cheap: a detail page is a read, "similar games" is a vector lookup, browse is a filtered query, collections are cached pipeline runs, and insights are SQL aggregations. This is what makes a multi-page application feasible in the time available.
4. **Build the MVP, document the scale.** In a 2-day window we *build* the working application and *write up* the production/telemetry design. The deliverable is comprehensive; the built infrastructure is appropriately minimal. (The README's scaling section is documentation, not infrastructure.)

---

## 4. The "everything in GCP" decision

We committed to a **single cloud (GCP)** for the production target. The reasoning:

- **One IAM model, one VPC, one bill, one compliance boundary.** Fewer trust boundaries, simpler security posture.
- **Private networking** from compute to data (no public-internet hop), lower latency, and tighter access control.
- **Unified observability and billing** under one project.

This preference is the lens through which the data-layer decision (below) was re-evaluated and ultimately changed from an earlier Supabase proposal.

---

## 5. Decision log (ADR-style)

Each decision records: the choice, why, the alternatives rejected, and the sprint-vs-production nuance.

### ADR-1 — Data + vector store: PostgreSQL + `pgvector`

**Decision.** Use PostgreSQL with the `pgvector` extension as the single store for the cleaned catalog, the enrichment, and the embeddings. **Local Postgres in Docker for development; Cloud SQL for PostgreSQL on deploy.**

**Why.**
- One store holds catalog metrics + enrichment + vectors together — no second system to keep in sync.
- At 455 rows, vector similarity is trivial; an index isn't even strictly required (a sequential scan is instant). `pgvector` scales comfortably well beyond this catalog.
- **Postgres everywhere means no migration and nothing leaves GCP.** The only thing that changes between dev and prod is `DATABASE_URL`.
- Cloud SQL keeps the data layer inside the GCP project (IAM, private IP, monitoring), satisfying the single-cloud principle.

**Alternatives considered.**
- **Supabase** (earlier proposal). Excellent DX (Postgres + `pgvector` + storage + API + dashboard, free tier). *Rejected* for production because it sits **outside GCP** — second vendor, public network hop, separate auth/compliance boundary — and its bundled extras (object storage, CDN) are deferrable wins at this scale.
- **AlloyDB for PostgreSQL.** Postgres-compatible with a stronger vector engine (ScaNN index). *Rejected as overkill* — pays off only at hundreds of thousands–millions of vectors. It is the documented **upgrade path**, not the start.
- **Vertex AI Vector Search.** Dedicated, scales to billions, but bills hourly for a deployed index endpoint **and** is a separate system from the metadata store. *Rejected* until pgvector genuinely can't keep up.
- **Pinecone / external vector DB.** A second system *and* off-GCP. *Rejected* — no benefit at this scale, contradicts single-cloud.

**Sprint vs production.** Dev: local Postgres + `pgvector` (Docker). Prod: Cloud SQL + `pgvector`. Upgrade path if vectors balloon: AlloyDB, then Vertex AI Vector Search.

---

### ADR-2 — Compute: Cloud Run

**Decision.** Run the application as a container on **Cloud Run**.

**Why.**
- Serverless, **scales to zero**, request-priced — ideal for bursty discovery traffic.
- Plain container, no cluster to operate.
- Native, simple connections to Cloud SQL and Secret Manager; fits the single-cloud posture.

**Alternatives considered.**
- **GKE (Kubernetes).** *Rejected* — operational weight unjustified for a single service at this scale.
- **App Engine.** Viable, but Cloud Run's container model is more portable and the better default today.
- **Compute Engine VM.** *Rejected* — manual ops, no scale-to-zero.

**Sprint vs production.** Identical. One `gcloud run deploy` of the container.

---

### ADR-3 — Backend framework + packaging: FastAPI serving the multi-page React build

**Decision.** A **FastAPI** service that exposes the API *and* serves the compiled multi-page React app (a single static bundle) from the same container.

**Why FastAPI.**
- The recommendation pipeline is **I/O-bound** — the slow step is calling web search for each shortlisted game. Async lets us **fan those calls out in parallel** instead of paying for them serially.
- **Pydantic** gives typed schemas for both the LLM's structured output and the API responses — half the anti-hallucination story is validating shapes before they ship.

**Why single-container packaging.** The React app (multiple routes via React Router — see ADR-4) builds to one `dist/` bundle. FastAPI serves it at `/` and the API at `/api/*`: **one container, one Cloud Run service, no CORS, one deploy.** A major simplification for a 2-day timeline with no real downside for an MVP.

**Alternatives considered.**
- **Two services (separate frontend host + API).** Cleaner separation for a large product, but adds a second deploy, CORS, and config overhead we don't need yet.
- **Streamlit / Gradio as the whole app.** *Rejected* — polish ceiling too low for a "polished recommendation screen", and they don't support a real multi-page experience cleanly. Kept as a **fallback** only if Day 2 runs out of time.

**Sprint vs production.** Single container now. If the product grows, split into FastAPI API + a dedicated frontend host (Firebase Hosting / Cloud Run static) — the API contract already supports it.

---

### ADR-4 — Frontend: React + Vite + Tailwind + shadcn/ui + React Router (multi-page)

**Decision.** A small **multi-page** React application (Vite) with client-side routing via **React Router**, styled with Tailwind and shadcn/ui. Pages: Discover, Results, Game detail, Browse, Collections, Insights (see ADR-5 for the product rationale).

**Why React + Vite + Tailwind + shadcn/ui.**
- The brief explicitly wants a **"polished recommendation screen."** Streamlit/Gradio have a hard polish ceiling; React does not.
- Tailwind + shadcn/ui deliver clean, consistent components **without building a design system from scratch** — exactly the leverage a short build needs.

**Why React Router (multi-page) over a single-screen SPA.**
- The product is richer than one search box (ADR-5), and **deep-linkable, navigable pages** (`/game/:id`, `/collections/:slug`, sharable `/results?vibe=...`) are a better experience and better product signal.
- React Router gives genuinely separate pages while **still compiling to one static bundle** — so the single-container deploy (ADR-3) is preserved.

**Alternatives considered.**
- **Single-screen SPA (one view).** *Rejected* — under-uses the rich enriched data and shows less product thinking.
- **Next.js (server-rendered MPA).** Real file-based pages and SEO, but reintroduces a Node server or a static-export step and **complicates the single-container Cloud Run model**. *Rejected* for this build; reasonable later if SEO/SSR matters.
- **Streamlit/Gradio.** See ADR-3 — fallback only.

**Sprint vs production.** Same stack scales fine. Production adds full loading/empty/error states (already planned), accessibility passes, and analytics.

---

### ADR-5 — Product surface: a small multi-page app, not a single search screen

**Decision.** Build a focused **multi-page product** rather than a lone vibe-search box:
- **Discover** — the vibe search (the centerpiece) with example chips, "Surprise me", and post-result refinement.
- **Results** — the five recommendations on a sharable route.
- **Game detail** — full metrics + enrichment + modern reputation + **Similar games** (vector nearest-neighbors).
- **Browse** — filterable/sortable catalog grid.
- **Collections / Moods** — curated, pre-baked vibes ("Cozy after-work", "Eerie sci-fi solitude", "Hidden gems", …).
- **Insights** — a data-viz dashboard over the cleaned catalog.

**Why.**
- It **demonstrates real product thinking** and uses the rich data we worked to build, instead of hiding it behind one input.
- It **serves the business objective** — *reignite interest in the older catalog* — directly: Collections, the Hidden-gems quadrant on Insights, and Similar-games all surface buried titles.
- It is **cheap**, per principle §3.3: every page is a thin layer over the catalog/embeddings/pipeline we already have — a detail read, a vector lookup, a filtered query, cached pipeline runs, or SQL aggregations.

**Alternatives considered.**
- **Single search screen only.** *Rejected* — minimal product signal; wastes the enrichment.
- **A sprawling app (accounts, social, library sync, reviews).** *Rejected* — scope creep far beyond two days; not what the brief asks for.

**Sprint vs production (prioritized cut).** Must-have core: **Discover + Results + Game detail (with Similar games)**. Comprehensiveness adds: **Collections + Insights**. Fast-follow: **Browse**. If all of it must ship inside two days, the trade is dropping the Cloud Run deploy stretch and easing the polish bar per page. Production would layer on saved/shortlisted games, history, and richer collections.

---

### ADR-6 — LLM + embeddings: Gemini API (direct), behind a thin abstraction

**Decision.** Use the **Gemini API directly** for both the LLM calls (vibe parsing, rationale) and embeddings (`text-embedding-004`), wrapped in a thin client so the provider can be swapped in one file.

**Why.**
- **One key covers both** LLM and embeddings — fewer moving parts in a sprint.
- Gemini Flash is cheap and fast for the parse + rationale calls; `text-embedding-004` covers the vectors.
- Going **direct (not Vertex) in the sprint** avoids the gcloud-auth/project setup that Vertex adds. Since the data layer is Cloud SQL, the "GCP-native" argument for Vertex is weaker for the MVP.

**Alternatives considered.**
- **Vertex AI (Gemini on Vertex).** The GCP-native production target. *Deferred to production* — the thin client makes the swap a one-file change. (Claude is also available on Vertex Model Garden.)
- **OpenAI / Anthropic direct.** Both strong. **Claude is a clean drop-in for the rationale step specifically** if richer prose is wanted there. Provider choice is intentionally abstracted.

**Sprint vs production.** Sprint: Gemini API direct. Prod: Vertex AI (GCP-native), same code path via the abstraction.

**As-built.** The originally-specified `text-embedding-004`/`gemini-1.5-flash` were retired mid-build; we migrated to `google-genai` with `gemini-embedding-001` (768-dim) + `gemini-2.5-flash` — the thin client made it a one-file change, exactly as designed.

---

### ADR-7 — Catalog enrichment + cover art: RAWG (or IGDB)

**Decision.** Enrich every title via the **RAWG** games-metadata API (IGDB/Twitch as the richer alternative): pull genres, tags, themes, a summary, and the cover image — in one batch pass, cached.

**Why.**
- This is the step that makes the product **possible at all** — it supplies the semantic substrate the CSV lacks (see §2) and feeds detail/browse/collections/insights/similar.
- It returns **cover art in the same call**, satisfying REQ-005/008 without a separate image pipeline.
- RAWG has a simple free tier and is fast to integrate; IGDB offers richer themes/keywords at the cost of Twitch OAuth.

**Alternatives considered.**
- **Pure LLM "knowledge" of each game.** *Rejected as primary* — risks hallucinated genres/summaries and no authoritative cover URL.
- **Web scraping / Wikipedia.** *Rejected* — brittle, inconsistent structure, no clean cover-art guarantee.

**Sprint vs production.** Same source. Production caches enrichment durably and refreshes on a schedule.

---

### ADR-8 — Live web reputation: Tavily

**Decision.** Use **Tavily** to fetch live web context for shortlisted candidates — "is this older title still worth playing today", recent sentiment, remaster news.

**Why.**
- Tavily is **purpose-built to feed an LLM live web context** (clean, summarized content) — precisely the brief's "how the community evaluates these older titles today" requirement (REQ-004, REQ-006 input #3).
- One API key; minimal integration.

**Alternatives considered.**
- **Vertex AI grounding with Google Search.** GCP-native production choice. *Deferred to production*.
- **Google Custom Search JSON API.** Workable, but returns raw results needing more post-processing.
- **Direct scraping.** *Rejected* — brittle and slow.

**Sprint vs production.** Sprint: Tavily. Prod: Vertex AI grounding (GCP-native). This is the **slowest, priciest** step, so it is the first thing cached and parallelized (ADR-10, ADR-11).

---

### ADR-9 — Ranking: deterministic weighted score in code (not the LLM)

**Decision.** Compute the final relevance ranking as a **transparent weighted score in application code**, blending three inputs: vibe-semantic similarity, the 2022 catalog metrics, and the modern web-reputation score. The LLM only (a) parses the vibe into structured attributes and (b) writes the per-game rationale.

**Why.**
- **Determinism and debuggability.** A weighted formula is reproducible, explainable, and tunable — the heart of the brief's "deterministic behavior" ask.
- It cleanly **separates the three required inputs** (REQ-006) into named, weighted terms.
- The model still contributes a *bounded, grounded* reputation score (0–1) from fetched web text, but never decides the ordering.

**Alternatives considered.**
- **LLM re-ranker over the full catalog.** *Rejected* — non-deterministic, doesn't scale, hard to explain; exactly the pattern the brief warns against.

**Sprint vs production.** Same. Weights start at sensible defaults and are tuned against an evaluation set.

---

### ADR-10 — Retrieval strategy: hybrid (vector + metric)

**Decision.** Embed each enriched game once; at query time, embed the vibe, pull the top ~20–30 by vector similarity via a Postgres function, then re-score that shortlist with the hard metrics.

**Why.**
- **Vector search** captures the semantic vibe match against the enriched text.
- **Metric re-scoring** lets situational signals matter — "after work" biases toward shorter `TIME`; `RATING`/completion are quality priors; `GAMERS` (log-scaled) is a popularity prior.
- A small shortlist keeps the **expensive web step** (ADR-8) cheap and parallelizable.
- The same `match_games` function powers **Similar games** on detail pages (nearest neighbors of a game's own embedding) — no LLM, near-free.

**Alternatives considered.**
- **Pure vector search.** Misses situational/quality signals.
- **LLM over the entire catalog.** See ADR-9 — rejected for determinism/scale.

---

### ADR-11 — Caching: one code path, file in dev → Memorystore (Redis) in production

**Decision.** Cache aggressively behind a single abstraction that switches on `REDIS_URL`: a
title-keyed **JSON file** with a TTL for dev, **Memorystore (Redis)** in production.

**Why.**
- The web-search calls are **where latency and cost live.** Cache per-game web reputation (TTL day–week); enrichment + cover URLs are baked into the catalog at ingestion.
- One code path ([cache.py](../backend/app/clients/cache.py)) means dev and prod differ only by config — the brief's **response caching** requirement, satisfied without a dev/prod fork.

**Alternatives considered.** No cache (*rejected* — slow/expensive); in-memory dict only (*rejected for prod* — lost on cold start, not shared).

**As-built.** File cache (`data/web_reputation_cache.json`) by default; set `REDIS_URL` and the same code writes to the Memorystore that [infra/](../infra/) provisions. Both implemented and deployed.

---

### ADR-12 — Cover-art delivery: RAWG URL now, Cloud Storage + CDN at hardening

**Decision.** For the MVP, store and render RAWG's image URL directly. During hardening, **re-host covers in Cloud Storage behind Cloud CDN**.

**Why.**
- Direct URLs get the MVP working immediately and keep object storage off the critical path.
- Re-hosting later guarantees availability, dedups, serves fast via CDN, and avoids **hotlinking / terms-of-service** risk on REQ-005/008.

---

### ADR-13 — Platform & ops: Secret Manager, Cloud Build + Artifact Registry, Cloud Logging/Monitoring

**Decision.** Standard GCP production hygiene under one project and IAM: Secret Manager for keys/creds; Cloud Build → Artifact Registry → Cloud Run for CI/CD from GitHub; Cloud Logging/Monitoring for observability.

**Why.** Single-cloud security and operability. Observability watches the four numbers that matter: **latency, cache-hit rate, token spend, and fallback rate.**

**As-built (implemented & deployed).** Secret Manager holds all four secrets (incl. an assembled `DATABASE_URL`, so the DB password never sits in plain Cloud Run env). A **2nd-gen** Cloud Build GitHub trigger builds → pushes to Artifact Registry → deploys Cloud Run on every push to `main` ([infra/cicd.tf](../infra/cicd.tf), [cloudbuild.yaml](../cloudbuild.yaml)). Terraform ([infra/](../infra/)) captures the entire stack as code — not optional, it's how the deploy happened.

---

### ADR-14 — Deliberate non-systems (what we are NOT using, and why)

Restraint is part of the design. We are deliberately **not** using:

- **Vertex AI Vector Search / AlloyDB** — unjustified cost/complexity below hundreds of thousands–millions of vectors. `pgvector` is enough.
- **Pinecone or any external vector DB** — a second system *and* off-GCP, for no benefit at this scale.
- **GKE / Kubernetes** — Cloud Run covers compute without cluster ops.
- **Pub/Sub + Dataflow / Kafka** — that is the **live-telemetry pipeline we *describe*** in the README scaling section, not something built in two days.

Keeping the system count low is what makes a comprehensive deliverable fit a 2-day timeline.

---

## 6. Anti-hallucination & determinism rationale

The brief tests for deterministic behavior and hallucination prevention; the as-built system
enforces it at several layers (the README determinism table maps each to its code):

1. **The model can't invent games.** It only sees the 5 candidate games passed to it (drawn from the DB) — structurally unable to introduce a title outside the catalog.
2. **Structured, temp-0 outputs.** Vibe parsing and rationale use **JSON schemas** (Pydantic-validated) at **temperature 0** with thinking disabled.
3. **Ranking is code, not the model** (ADR-9).
4. **Reputation is deterministic.** Web sentiment is a fixed lexicon over fetched text — same text ⇒ same score (an as-built delta from the original LLM-extraction plan; no model in the loop here).
5. **Rationale is grounded.** Per-game rationale draws only on that game's enrichment fields + fetched web snippets; the prompt forbids unsupported claims and any title not in the list.
6. **Cover-art fallback.** Dead/missing cover URLs fall back to a generated tile client-side (`CoverImage.tsx`) — art is never fabricated.

---

## 7. Data-freshness caveat (stated honestly)

The catalog is **locked to 2022 by design** (the brief's "static legacy catalog" framing). Correct for this exercise. For real production, some 2022 titles have since left Game Pass — so a **freshness reconciliation** against the live catalog is required before anything customer-facing. We flag this rather than pretend the snapshot is current.

---

## 8. Final stack at a glance

| Layer | System | Role | Sprint → Production |
|---|---|---|---|
| Client | React + Vite + Tailwind + shadcn/ui + React Router | Polished multi-page UI | Same |
| Application | FastAPI on Cloud Run | API + orchestration + deterministic ranking; serves the React build | Same (optionally split services) |
| Data | PostgreSQL + `pgvector` | Catalog + enrichment + embeddings | Local Docker → Cloud SQL |
| Data | Cache | Web-reputation / result caching (one code path, `REDIS_URL`) | JSON file → Memorystore (Redis) |
| Data | Cover art store | Official cover images | RAWG URL → Cloud Storage + Cloud CDN |
| External | Gemini API | LLM (parse, rationale) + embeddings | Direct → Vertex AI |
| External | RAWG / IGDB | Semantic enrichment + cover art | Same (external; no GCP equivalent) |
| External | Tavily | Live web reputation | Tavily → Vertex AI grounding |
| Platform | Secret Manager | Keys / credentials | Same |
| Platform | Cloud Build + Artifact Registry | CI/CD from GitHub | Same |
| Platform | Cloud Logging + Monitoring | Observability | Same |

**One line:** almost the entire system is GCP-native; only three external API providers sit outside GCP, and two of those (Gemini, Tavily) have GCP-native production swaps — leaving RAWG/IGDB as the sole irreducible external dependency.
