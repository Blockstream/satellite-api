resource "google_compute_firewall" "satapi-lb" {
  name    = "${var.name}-fw-rule-${var.env}"
  network = data.google_compute_network.satapi-lb.self_link
  project = var.project
  count   = var.create_resources

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  target_service_accounts = [
    google_service_account.satapi-lb[0].email,
  ]
}

resource "google_compute_firewall" "satapi-lb-prom" {
  name    = "${var.name}-prometheus-access-${var.env}"
  network = data.google_compute_network.satapi-lb.self_link
  project = var.project
  count   = var.create_resources

  allow {
    protocol = "tcp"
    ports    = ["9100"]
  }

  source_service_accounts = [
    var.prom_service_acct,
  ]

  target_service_accounts = [
    google_service_account.satapi-lb[0].email,
  ]
}

