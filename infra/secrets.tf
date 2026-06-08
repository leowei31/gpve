# Secret Manager holds all credentials (ADR-13) — never baked into the image or plain env.
# API-key VALUES come from sensitive variables (terraform.tfvars / TF_VAR_*, never committed).
# DATABASE_URL is assembled here so the DB password stays out of Cloud Run's plain env.

# Keep the (non-sensitive) secret names separate from the (sensitive) values so neither
# for_each touches a sensitive value — Terraform forbids sensitive for_each keys.
locals {
  api_key_secret_ids = {
    gemini = "gpve-gemini-api-key"
    rawg   = "gpve-rawg-api-key"
    tavily = "gpve-tavily-api-key"
  }
  api_key_values = {
    gemini = var.gemini_api_key
    rawg   = var.rawg_api_key
    tavily = var.tavily_api_key
  }
}

resource "google_secret_manager_secret" "api_keys" {
  for_each  = local.api_key_secret_ids
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled]
}

# A working deploy needs all three keys set (see the README runbook); an empty payload here
# fails fast at apply rather than deploying a broken service.
resource "google_secret_manager_secret_version" "api_keys" {
  for_each = local.api_key_secret_ids

  secret      = google_secret_manager_secret.api_keys[each.key].id
  secret_data = local.api_key_values[each.key]
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "gpve-database-url"

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled]
}

resource "google_secret_manager_secret_version" "database_url" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = "postgresql://${var.db_user}:${random_password.db.result}@${google_sql_database_instance.pg.private_ip_address}:5432/${var.db_name}"
}
