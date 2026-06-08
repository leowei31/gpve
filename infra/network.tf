# Private networking so Cloud Run reaches Cloud SQL and Memorystore over RFC1918 only.
#
#   Cloud Run --(Serverless VPC Access connector)--> VPC --(private services access peering)-->
#   Cloud SQL private IP  +  Memorystore private IP
#
# External APIs (Gemini/RAWG/Tavily) still egress to the internet (egress = PRIVATE_RANGES_ONLY
# on the service keeps only private traffic on the connector).

resource "google_compute_network" "vpc" {
  name                    = "gpve-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.enabled]
}

# Serverless VPC Access connector — the bridge from Cloud Run/Jobs into the VPC.
resource "google_vpc_access_connector" "connector" {
  name          = "gpve-connector"
  region        = var.region
  network       = google_compute_network.vpc.id
  ip_cidr_range = "10.8.0.0/28"
  min_instances = 2 # newer provider requires explicit scaling; 2/3 are the minimums (cheapest)
  max_instances = 3
  depends_on    = [google_project_service.enabled]
}

# Reserved range + peering for Private Services Access (Cloud SQL + Memorystore private IPs).
resource "google_compute_global_address" "private_ip_range" {
  name          = "gpve-private-ip-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
}
