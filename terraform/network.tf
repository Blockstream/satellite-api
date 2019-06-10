# IP address
resource "google_compute_address" "lb" {
  name    = "satellite-api-client-lb-${local.env}"
  region  = var.region
  project = var.project
  count   = local.create_mainnet
}

# Forwarding rules
resource "google_compute_forwarding_rule" "rule-https" {
  name        = "satellite-api-https-forwarding-rule-${local.env}"
  target      = google_compute_target_pool.blc-pool[0].self_link
  port_range  = "443"
  ip_protocol = "TCP"
  ip_address  = google_compute_address.lb[0].address
  region      = var.region
  project     = var.project
  count       = local.create_mainnet
}

resource "google_compute_forwarding_rule" "rule-http" {
  name        = "satellite-api-http-forwarding-rule-${local.env}"
  target      = google_compute_target_pool.blc-pool[0].self_link
  port_range  = "80"
  ip_protocol = "TCP"
  ip_address  = google_compute_address.lb[0].address
  region      = var.region
  project     = var.project
  count       = local.create_mainnet
}

resource "google_compute_target_pool" "blc-pool" {
  name    = "satellite-api-target-pool-${local.env}"
  region  = var.region
  project = var.project
  count   = local.create_mainnet

  health_checks = [
    google_compute_http_health_check.blc-health[0].self_link
  ]
}

resource "google_compute_http_health_check" "blc-health" {
  name    = "satellite-api-http-health-${local.env}"
  project = var.project
  count   = local.create_mainnet

  timeout_sec        = 5
  check_interval_sec = 10

  host         = "${local.env == "staging" ? "staging-" : ""}api.blockstream.space"
  port         = "80"
  request_path = "/healthz"
}
