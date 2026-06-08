variable "project_id" {
  description = "Target GCP project ID (must have billing enabled)."
  type        = string
}

variable "region" {
  description = "GCP region for all regional resources."
  type        = string
  default     = "us-central1"
}

# --- Container image -----------------------------------------------------------
variable "image_name" {
  description = "Image name within the Artifact Registry repo."
  type        = string
  default     = "gpve"
}

variable "image_tag" {
  description = "Image tag to deploy (e.g. a git SHA or 'latest'). Push before the full apply."
  type        = string
  default     = "latest"
}

# --- Cloud SQL -----------------------------------------------------------------
variable "db_tier" {
  description = "Cloud SQL machine tier. db-f1-micro is cheapest; bump for real load."
  type        = string
  default     = "db-f1-micro"
}

variable "db_name" {
  description = "Application database name."
  type        = string
  default     = "gpve"
}

variable "db_user" {
  description = "Application database user."
  type        = string
  default     = "gpve"
}

variable "db_public_ip" {
  description = <<-EOT
    Also give Cloud SQL a public IP (with no authorized networks) so the catalog can be
    seeded from an operator machine via the Cloud SQL Auth Proxy. The app always uses the
    private IP. Set false for a private-IP-only instance (seed via the Cloud Run Job instead).
  EOT
  type        = bool
  default     = true
}

variable "db_deletion_protection" {
  description = "Guard against accidental instance deletion. Set false to make teardown easy."
  type        = bool
  default     = false
}

# --- Memorystore (Redis) -------------------------------------------------------
variable "redis_memory_gb" {
  description = "Memorystore capacity in GB (BASIC tier minimum is 1)."
  type        = number
  default     = 1
}

# --- Cloud Run scaling ---------------------------------------------------------
variable "min_instances" {
  description = "Cloud Run min instances. 0 = scale to zero (cheap, cold starts); 1 = warm."
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Cloud Run max instances."
  type        = number
  default     = 4
}

variable "allow_unauthenticated" {
  description = "Make the Cloud Run service publicly reachable (demo). False = IAM-gated."
  type        = bool
  default     = true
}

# --- Secrets (provide via terraform.tfvars or TF_VAR_*, never commit) ----------
variable "gemini_api_key" {
  description = "Gemini API key (Secret Manager value)."
  type        = string
  sensitive   = true
  default     = ""
}

variable "rawg_api_key" {
  description = "RAWG API key (Secret Manager value). Only needed by the seed/enrich Job."
  type        = string
  sensitive   = true
  default     = ""
}

variable "tavily_api_key" {
  description = "Tavily API key (Secret Manager value)."
  type        = string
  sensitive   = true
  default     = ""
}

# --- CI/CD (optional; needs a connected GitHub repo) ---------------------------
variable "enable_ci_trigger" {
  description = "Create a Cloud Build trigger. Requires github_owner/github_repo to be set."
  type        = bool
  default     = false
}

variable "github_owner" {
  description = "GitHub owner/org for the Cloud Build trigger (if enable_ci_trigger)."
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repo name for the Cloud Build trigger (if enable_ci_trigger)."
  type        = string
  default     = ""
}

variable "github_connection_name" {
  description = <<-EOT
    Short name of the 2nd-gen Cloud Build host connection created in the Console
    (Cloud Build > Repositories > 2nd gen). Must be created in `region`. Required when
    enable_ci_trigger = true.
  EOT
  type        = string
  default     = ""
}

variable "github_branch" {
  description = "Branch regex the Cloud Build trigger fires on."
  type        = string
  default     = "^main$"
}
