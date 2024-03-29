resource "google_compute_address" "satapi-lb-internal" {
  name         = "${var.name}-internal-ip-${var.env}"
  address_type = "INTERNAL"
  project      = var.project
  region       = var.region
  count        = var.create_resources
}

resource "google_compute_backend_service" "satapi-lb" {
  name        = "${var.name}-backend-service-${var.env}"
  description = "Satellite API"
  protocol    = "HTTP"
  port_name   = "http"
  project     = var.project
  count       = var.create_resources

  backend {
    group = google_compute_region_instance_group_manager.satapi-lb[0].instance_group
  }

  health_checks = [var.health_check]
}

resource "google_compute_backend_service" "satapi-lb-tor" {
  name        = "${var.name}-tor-backend-service-${var.env}"
  description = "Satellite API Tor"
  protocol    = "HTTP"
  port_name   = "http81"
  project     = var.project
  count       = var.env == "staging" ? 0 : var.create_resources

  backend {
    group = google_compute_region_instance_group_manager.satapi-lb[0].instance_group
  }

  health_checks = [var.health_check]
}