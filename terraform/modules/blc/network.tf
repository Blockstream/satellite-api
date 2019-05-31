resource "google_compute_address" "blc" {
  name    = "${var.name}-${var.net}-external-ip-${var.env}-${count.index}"
  project = var.project
  region  = var.region
  count   = var.create_resources
}

# Backend service
resource "google_compute_backend_service" "blc" {
  name        = "${var.name}-${var.net}-backend-service-${var.env}"
  description = "Satellite API"
  protocol    = "HTTP"
  port_name   = "http"
  timeout_sec = var.timeout
  count       = var.create_resources

  backend {
    group = google_compute_instance_group_manager.blc[0].instance_group
  }

  health_checks = [google_compute_health_check.blc[0].self_link]
}

# Health checks
resource "google_compute_health_check" "blc" {
  name  = "${var.name}-${var.net}-health-check-${var.env}"
  count = var.create_resources

  check_interval_sec = 5
  timeout_sec        = 3

  tcp_health_check {
    port = "80"
  }
}

