# IP addresses
resource "google_compute_address" "blc" {
  name    = "${var.name}-external-ip-${var.env}-${count.index}"
  project = "${var.project}"
  region  = "${var.region}"
  count   = "${var.create_resources}"
}

resource "google_compute_global_address" "lb" {
  name    = "${var.name}-client-lb-${var.env}"
  project = "${var.project}"
  count   = "${var.create_resources}"
}

# FW rules
resource "google_compute_firewall" "blc" {
  name    = "${var.name}-fw-rule-${var.env}"
  network = "${data.google_compute_network.blc.self_link}"
  count   = "${var.create_resources}"

  allow {
    protocol = "tcp"
    ports    = ["18333", "9735", "80"]
  }

  target_service_accounts = [
    "${google_service_account.blc.email}",
  ]
}

resource "google_compute_firewall" "blc-prom" {
  name    = "${var.name}-prometheus-access-${var.env}"
  network = "${data.google_compute_network.blc.self_link}"
  count   = "${var.create_resources}"

  allow {
    protocol = "tcp"
    ports    = ["9100"]
  }

  source_service_accounts = [
    "${var.prom_service_acct}",
  ]

  target_service_accounts = [
    "${google_service_account.blc.email}",
  ]
}

# Backend service
resource "google_compute_backend_service" "blc" {
  name        = "${var.name}-backend-service-${var.env}"
  description = "Satellite API"
  protocol    = "HTTP"
  port_name   = "http"
  timeout_sec = "${var.timeout}"
  count       = "${var.create_resources}"

  backend {
    group = "${google_compute_instance_group_manager.blc.instance_group}"
  }

  health_checks = ["${google_compute_health_check.blc.self_link}"]
}

# Health checks
resource "google_compute_health_check" "blc" {
  name  = "${var.name}-health-check-${var.env}"
  count = "${var.create_resources}"

  check_interval_sec = 5
  timeout_sec        = 3

  tcp_health_check {
    port = "80"
  }
}
