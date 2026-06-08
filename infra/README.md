# GPVE infrastructure (Terraform → GCP)

Infrastructure-as-code for the production target in [docs/DESIGN_RATIONALE.md](../docs/DESIGN_RATIONALE.md)
(ADR-1/2/3/11/13) and [docs/IMPLEMENTATION_PLAN.md](../docs/IMPLEMENTATION_PLAN.md) §10.

> **Note:** the take-home brief only requires a *locally runnable* app plus a *written* scaling
> proposal — it does **not** require a live deploy. This Terraform is beyond-scope: it turns the
> documented architecture into something you can actually `apply`.

## What it provisions

| Resource | Purpose |
|---|---|
| `google_project_service` | Enables run / sqladmin / secretmanager / artifactregistry / compute / vpcaccess / servicenetworking / redis / cloudbuild / cloudscheduler |
| VPC + Serverless VPC connector + private services access | Cloud Run reaches the data tier over RFC1918 only |
| Cloud SQL (Postgres 16) + db + user | Catalog + enrichment + 768-dim embeddings (`pgvector`) |
| Memorystore (Redis, BASIC) | Production web-reputation cache (`REDIS_URL`) |
| Artifact Registry (Docker) | Holds the single GPVE image |
| Secret Manager ×4 | `gemini` / `rawg` / `tavily` keys + assembled `DATABASE_URL` |
| Cloud Run **service** `gpve` | The app (FastAPI API + React SPA), private DB/Redis egress |
| Cloud Run **job** `gpve-seed` | `python -m ingest.seed` — schema + catalog load / re-load |
| Cloud Build trigger *(optional)* | Build → push → deploy on git push (needs GitHub connected) |

## Prerequisites

1. **A GCP project with billing enabled**, and these tools locally:
   - `terraform` ≥ 1.5 (have: 1.14), `gcloud` CLI, Docker, and `cloud-sql-proxy` (only if seeding via the Auth Proxy).
2. Authenticate Terraform (Application Default Credentials):
   ```bash
   gcloud auth application-default login
   gcloud auth configure-docker us-central1-docker.pkg.dev   # match your region
   ```
3. `cp terraform.tfvars.example terraform.tfvars` and fill in `project_id` + the three API keys
   (or export them as `TF_VAR_gemini_api_key`, etc. — `terraform.tfvars` is gitignored).

## Deploy (first time)

The Cloud Run service needs the image to exist, so apply in two phases.

```bash
cd infra
terraform init

# Phase 1 — enable APIs + create the registry only
terraform apply -target=google_project_service.enabled \
                -target=google_artifact_registry_repository.repo

# Build + push the image (from the repo root)
cd ..
REGION=us-central1; PROJECT=$(gcloud config get-value project)
docker build -t $REGION-docker.pkg.dev/$PROJECT/gpve/gpve:latest .
docker push   $REGION-docker.pkg.dev/$PROJECT/gpve/gpve:latest

# Phase 2 — everything else (VPC, Cloud SQL, Redis, secrets, Cloud Run, job)
cd infra
terraform apply
```

## Seed the catalog (one-time, and after any catalog refresh)

The database starts empty. The image bakes in the committed caches, so the **Cloud Run Job**
applies the schema and loads all 446 games with no laptop DB access:

```bash
gcloud run jobs execute gpve-seed --region us-central1 --wait
```

<details><summary>Alternative: seed from your machine via the Auth Proxy (needs <code>db_public_ip = true</code>)</summary>

```bash
cloud-sql-proxy $(terraform output -raw sql_connection_name) &   # 127.0.0.1:5432
cd ../backend
DATABASE_URL="postgresql://gpve:$(cd ../infra && terraform output -raw db_password)@127.0.0.1:5432/gpve" \
  ../.venv/Scripts/python -m ingest.seed
```
</details>

## Verify

```bash
curl "$(terraform output -raw service_url)/api/health"     # {"games": 446, ...}
open  "$(terraform output -raw service_url)"               # the SPA
```

## Ongoing deploys

Either re-run the phase-2 build/push + `terraform apply` with a new `image_tag`, or enable CI
(`enable_ci_trigger = true` + `github_owner`/`github_repo`, after connecting the repo in
**Cloud Build → Repositories**) so [/cloudbuild.yaml](../cloudbuild.yaml) runs on every push.

## Teardown

```bash
terraform destroy
```

`db_deletion_protection` defaults to **false** for easy teardown — flip it to `true` for
anything real.

## ⚠️ Cost

Always-on pieces bill even when Cloud Run is scaled to zero — mainly **Memorystore** (~$35/mo),
the **VPC connector** (~$9/mo), and **Cloud SQL** `db-f1-micro` (~$8–10/mo). Budget roughly
**$50–60/month** if left running. **`terraform destroy` when you're done demoing.** To trim:
set `redis_memory_gb` low, leave `min_instances = 0`, and drop Memorystore if the file/Postgres
cache is acceptable.

## Design notes

- **One image, two workloads.** The Cloud Run service serves; the Cloud Run job seeds/re-loads.
  Same artifact, different entrypoint — no drift.
- **Private data tier.** Cloud SQL + Redis are private-IP; only Gemini/RAWG/Tavily egress to the
  internet (`egress = PRIVATE_RANGES_ONLY` on the connector).
- **Secrets never in the image or plain env** — Secret Manager refs, including a fully-assembled
  `DATABASE_URL` so the DB password stays out of Cloud Run's environment.
- **`REDIS_URL` toggles the cache backend** in code ([app/clients/cache.py](../backend/app/clients/cache.py)):
  set → Memorystore, unset → the local JSON file. Dev and prod share one code path.
