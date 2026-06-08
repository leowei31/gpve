# Cloud SQL for PostgreSQL 16 + pgvector (ADR-1). Private IP for the app; an optional public IP
# (no authorized networks) lets an operator seed the catalog via the Cloud SQL Auth Proxy.
# The `vector` extension is created by sql/01_schema.sql during the seed step (no flag needed).

resource "random_password" "db" {
  length  = 32
  special = false # keep it URL-safe for DATABASE_URL
}

resource "google_sql_database_instance" "pg" {
  name             = "gpve-postgres"
  database_version = "POSTGRES_16"
  region           = var.region

  deletion_protection = var.db_deletion_protection
  depends_on          = [google_service_networking_connection.private_vpc_connection]

  settings {
    tier              = var.db_tier
    edition           = "ENTERPRISE" # shared-core tiers (db-f1-micro) require ENTERPRISE, not ENTERPRISE_PLUS
    availability_type = "ZONAL"
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled    = var.db_public_ip
      private_network = google_compute_network.vpc.id
      # No authorized_networks: even with a public IP, access is only via the Auth Proxy (IAM).
    }

    backup_configuration {
      enabled = true
    }
  }
}

resource "google_sql_database" "app" {
  name     = var.db_name
  instance = google_sql_database_instance.pg.name
}

resource "google_sql_user" "app" {
  name     = var.db_user
  instance = google_sql_database_instance.pg.name
  password = random_password.db.result
}
