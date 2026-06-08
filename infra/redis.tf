# Memorystore (Redis) — the production web-reputation cache (ADR-11). The app uses it whenever
# REDIS_URL is set (see app/clients/cache.py); otherwise it falls back to the local JSON file.
# PRIVATE_SERVICE_ACCESS reuses the same peering range as Cloud SQL.
resource "google_redis_instance" "cache" {
  name               = "gpve-cache"
  tier               = "BASIC"
  memory_size_gb     = var.redis_memory_gb
  region             = var.region
  authorized_network = google_compute_network.vpc.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"
  redis_version      = "REDIS_7_0"

  depends_on = [
    google_project_service.enabled,
    google_service_networking_connection.private_vpc_connection,
  ]
}
