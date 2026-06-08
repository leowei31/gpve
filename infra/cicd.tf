# Optional CI/CD: build + push the image and deploy Cloud Run on push to the default branch
# (ADR-13), using a 2nd-generation Cloud Build GitHub connection.
#
# The GitHub *connection* itself is created once in the Console (Cloud Build > Repositories,
# 2nd gen) because it needs an interactive OAuth / GitHub-App install that can't be done in
# Terraform. Everything else — linking the repo, the runner service account, and the trigger —
# is managed here. Enable with `enable_ci_trigger = true` and set `github_connection_name`
# (plus github_owner/github_repo/github_branch) in terraform.tfvars.
#
# The build steps live in /cloudbuild.yaml so they also run via `gcloud builds submit`.

locals {
  github_remote_uri = "https://github.com/${var.github_owner}/${var.github_repo}.git"
}

# Link the GitHub repo to the console-created 2nd-gen connection.
resource "google_cloudbuildv2_repository" "github" {
  count             = var.enable_ci_trigger ? 1 : 0
  name              = var.github_repo
  location          = var.region
  parent_connection = var.github_connection_name
  remote_uri        = local.github_remote_uri
  depends_on        = [google_project_service.enabled]
}

# Dedicated runner SA — regional 2nd-gen builds require an explicit service account
# (the legacy {projectnum}@cloudbuild.gserviceaccount.com SA only works for global builds).
resource "google_service_account" "cicd" {
  count        = var.enable_ci_trigger ? 1 : 0
  account_id   = "gpve-cicd"
  display_name = "GPVE Cloud Build runner"
}

# Deploy to Cloud Run, act as the runtime SA (gpve-run), push images, and write build logs.
resource "google_project_iam_member" "cb_run_admin" {
  count   = var.enable_ci_trigger ? 1 : 0
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.cicd[0].email}"
}

resource "google_project_iam_member" "cb_sa_user" {
  count   = var.enable_ci_trigger ? 1 : 0
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.cicd[0].email}"
}

resource "google_project_iam_member" "cb_artifact_writer" {
  count   = var.enable_ci_trigger ? 1 : 0
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.cicd[0].email}"
}

resource "google_project_iam_member" "cb_log_writer" {
  count   = var.enable_ci_trigger ? 1 : 0
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cicd[0].email}"
}

resource "google_cloudbuild_trigger" "deploy" {
  count           = var.enable_ci_trigger ? 1 : 0
  name            = "gpve-deploy"
  location        = var.region
  service_account = google_service_account.cicd[0].id
  filename        = "cloudbuild.yaml"

  repository_event_config {
    repository = google_cloudbuildv2_repository.github[0].id
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

  depends_on = [
    google_project_service.enabled,
    google_project_iam_member.cb_run_admin,
    google_project_iam_member.cb_sa_user,
    google_project_iam_member.cb_artifact_writer,
    google_project_iam_member.cb_log_writer,
  ]
}
