# GPVE

---

## Implementation plan

**The catch that drives everything:** the CSV is all metrics (achievements, players, completion, rating) and has *zero* semantic fields, so you can't match a "vibe" to it directly. The fix is to enrich every game at ingestion (RAWG → genres, tags, themes, summary, cover art), embed that text, and match the vibe against the *enriched* layer.

**Stack** (all GCP except three API calls):
- Frontend: React + Vite + Tailwind + shadcn/ui, multi-page via React Router
- Backend: FastAPI on Cloud Run, also serving the React build — one container
- Data: Postgres + `pgvector` (local Docker for dev, Cloud SQL for prod — same code)
- LLM + embeddings: Gemini API (swappable to Vertex / Anthropic); enrichment + art: RAWG/IGDB; live web reputation: Tavily
- Cache: Postgres table now → Memorystore (Redis) later

**Pipeline** (vibe → 5 games): parse vibe into structured attributes (Gemini) → vector + metric retrieval (pgvector) → live web check on a shortlist (Tavily, cached) → **deterministic weighted ranking in code** → grounded per-game rationale (Gemini) → validate → 5 results with cover + rationale. Rule of thumb: the LLM does language, code does the ranking.

**Pages:** Discover (vibe search), Results (5 cards, sharable URL), Game detail (full metrics + reputation + *similar games* via vector lookup), Browse (filters), Collections (cached curated moods), Insights (catalog charts). Most are thin layers over the same catalog/pipeline.

---

## Design rationale

**The insight:** the data is all metrics, no genre/theme/mood — so enrichment at ingestion *is* the product. Match the vibe against enriched text, never the raw columns.

**All-GCP:** chosen for one IAM/VPC/bill/compliance boundary and private networking between compute and data.

**The big calls, one line each:**
- **Postgres + pgvector, not Supabase** — keeps everything in GCP and avoids a later migration. Supabase was faster to set up but off-GCP. Local Docker = dev, Cloud SQL = prod.
- **Cloud Run, not GKE** — serverless, scale-to-zero, no cluster to run.
- **FastAPI + React multi-page in one container** — async fits the I/O-bound web step; one bundle, one deploy, no CORS. Multi-page (React Router) over a single screen because the rich data deserves real pages and they're cheap to add.
- **Gemini (direct, abstracted)** — one key for LLM + embeddings; swaps to Vertex (prod) or Claude in one file.
- **RAWG/IGDB** — the enrichment that makes vibe-matching possible at all, plus cover art in the same call.
- **Tavily** — purpose-built live web context for "is this still good today"; → Vertex grounding in prod.
- **Deterministic ranking in code; LLM only for parsing + rationale** — reproducible, debuggable, and exactly what the brief's anti-hallucination ask wants.

**Deliberately not using:** AlloyDB / Vertex Vector Search / Pinecone (overkill at 455 rows), GKE (Cloud Run is enough), Pub/Sub + Dataflow (that's the documented *future* telemetry path, not the MVP).

**Anti-hallucination:** the model only picks from a passed candidate list, structured JSON at temperature 0, grounded + cited rationale, and a validation pass that drops any game not in the catalog or any dead cover URL.
