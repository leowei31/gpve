# Artifact Registry holds the single GPVE container image (built from the repo Dockerfile and
# pushed by Cloud Build or `docker push`). Cloud Run and the seed Job both pull from here.
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "gpve"
  format        = "DOCKER"
  description   = "GPVE application image (FastAPI API + React SPA, single container)."
  depends_on    = [google_project_service.enabled]
}
