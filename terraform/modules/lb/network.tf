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