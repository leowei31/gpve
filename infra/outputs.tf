output "service_url" {
  description = "Public URL of the GPVE Cloud Run service."
  value       = google_cloud_run_v2_service.app.uri
}

output "image" {
  description = "Fully-qualified image reference Cloud Run pulls (build + push this tag)."
  value       = local.image
}

output "artifact_registry" {
  description = "Docker push target prefix."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
}

output "sql_connection_name" {
  description = "Cloud SQL connection name for the Auth Proxy (project:region:instance)."
  value       = google_sql_database_instance.pg.connection_name
}

output "sql_private_ip" {
  description = "Cloud SQL private IP (what the app's DATABASE_URL points at)."
  value       = google_sql_database_instance.pg.private_ip_address
}

output "sql_public_ip" {
  description = "Cloud SQL public IP (Auth-Proxy seeding), if db_public_ip = true."
  value       = google_sql_database_instance.pg.public_ip_address
}

output "redis_host" {
  description = "Memorystore private host (the app builds REDIS_URL from this)."
  value       = google_redis_instance.cache.host
}

output "seed_job" {
  description = "Run this after deploy to load the catalog: gcloud run jobs execute <name>."
  value       = google_cloud_run_v2_job.seed.name
}

output "db_password" {
  description = "Generated DB password (for the Auth Proxy seed step)."
  value       = random_password.db.result
  sensitive   = true
}
