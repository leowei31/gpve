# Cloud Run service (the app) + Cloud Run Job (catalog seed / re-load), both on one image and
# one least-privilege service account, reaching the private data tier via the VPC connector.

resource "google_service_account" "run" {
  account_id   = "gpve-run"
  display_name = "GPVE Cloud Run runtime"
}

# Read secrets + connect to Cloud SQL. Redis needs no IAM (network-only access).
resource "google_project_iam_member" "cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.run.email}"
}

resource "google_secret_manager_secret_iam_member" "api_keys_accessor" {
  for_each  = google_secret_manager_secret.api_keys
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.run.email}"
}

resource "google_secret_manager_secret_iam_member" "database_url_accessor" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.run.email}"
}

# --- The application service ----------------------------------------------------
resource "google_cloud_run_v2_service" "app" {
  name                = "gpve"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false # allow Terraform to replace/destroy the service (demo infra)

  template {
    service_account = google_service_account.run.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = local.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.cache.host}:${google_redis_instance.cache.port}"
      }

      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.api_keys["gemini"].secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "TAVILY_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.api_keys["tavily"].secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_iam_member.api_keys_accessor,
    google_secret_manager_secret_iam_member.database_url_accessor,
  ]
}

# Public access for the demo (toggle with allow_unauthenticated). False = IAM-gated.
resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.allow_unauthenticated ? 1 : 0
  name     = google_cloud_run_v2_service.app.name
  location = google_cloud_run_v2_service.app.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- The seed / re-load Job ----------------------------------------------------
# Runs `python -m ingest.seed` (apply schema -> load the catalog from the baked-in caches).
# Trigger once after the first deploy, and again whenever the catalog/embeddings change:
#   gcloud run jobs execute gpve-seed --region <region>
resource "google_cloud_run_v2_job" "seed" {
  name     = "gpve-seed"
  location = var.region

  template {
    template {
      service_account = google_service_account.run.email

      vpc_access {
        connector = google_vpc_access_connector.connector.id
        egress    = "PRIVATE_RANGES_ONLY"
      }

      containers {
        image   = local.image
        command = ["python", "-m", "ingest.seed"]

        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.database_url.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_iam_member.database_url_accessor,
  ]
}
