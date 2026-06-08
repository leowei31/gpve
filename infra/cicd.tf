# Optional CI/CD: a Cloud Build trigger that builds + pushes the image and deploys Cloud Run on
# push to the default branch (ADR-13). Gated behind enable_ci_trigger because it needs the repo
# connected to Cloud Build's GitHub app first (Console: Cloud Build > Repositories). The build
# steps themselves live in /cloudbuild.yaml so they also run via `gcloud builds submit`.

data "google_project" "this" {
  project_id = var.project_id
}

locals {
  cloudbuild_sa = "serviceAccount:${data.google_project.this.number}@cloudbuild.gserviceaccount.com"
}

resource "google_cloudbuild_trigger" "deploy" {
  count    = var.enable_ci_trigger ? 1 : 0
  name     = "gpve-deploy"
  location = var.region
  filename = "cloudbuild.yaml"

  github {
    owner = var.github_owner
    name  = var.github_repo
    push {
      branch = var.github_branch
    }
  }

  substitutions = {
    _REGION  = var.region
    _REPO    = google_artifact_registry_repository.repo.repository_id
    _SERVICE = google_cloud_run_v2_service.app.name
    _IMAGE   = var.image_name
  }

  depends_on = [google_project_service.enabled]
}

# Let Cloud Build deploy to Cloud Run, push images, and act as the runtime SA.
resource "google_project_iam_member" "cb_run_admin" {
  count   = var.enable_ci_trigger ? 1 : 0
  project = var.project_id
  role    = "roles/run.admin"
  member  = local.cloudbuild_sa
}

resource "google_project_iam_member" "cb_sa_user" {
  count   = var.enable_ci_trigger ? 1 : 0
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = local.cloudbuild_sa
}

resource "google_project_iam_member" "cb_artifact_writer" {
  count   = var.enable_ci_trigger ? 1 : 0
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = local.cloudbuild_sa
}
