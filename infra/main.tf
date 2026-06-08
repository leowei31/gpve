# GPVE — Infrastructure as Code for the GCP production target.
#
# Mirrors DESIGN_RATIONALE.md (ADR-1/2/3/11/13) and IMPLEMENTATION_PLAN.md §10:
#   Cloud Run (one container: API + SPA)  ·  Cloud SQL Postgres 16 + pgvector  ·
#   Memorystore (Redis) for the web-reputation cache  ·  Artifact Registry  ·
#   Secret Manager  ·  a Cloud Run Job that seeds / re-loads the catalog.
#
# Everything reaches the data tier over a private VPC (Serverless VPC Access connector +
# private services access); only the three external APIs (Gemini/RAWG/Tavily) egress to the
# internet. See infra/README.md for the apply order and the one-time DB seed step.

terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

locals {
  # Fully-qualified image in Artifact Registry. The first apply can use a placeholder image
  # (var.image_tag against an empty repo) — see the README's two-phase apply.
  image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/${var.image_name}:${var.image_tag}"
}
