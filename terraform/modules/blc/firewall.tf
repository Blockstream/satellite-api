resource "google_compute_firewall" "blc" {
  name    = "${var.name}-${var.net}-fw-rule-${var.env}"
  network = data.google_compute_network.blc.self_link
  project = var.project
  count   = var.create_resources

  allow {
    protocol = "tcp"
    ports    = ["18333", "8333", "9735"]
  }

  target_service_accounts = [
    google_service_account.blc[0].email,
  ]
}

resource "google_compute_firewall" "api-internal" {
  name    = "${var.name}-${var.net}-lb-internal-fw-rule-${var.env}"
  network = data.google_compute_network.blc.self_link
  project = var.project
  count   = var.create_resources

  allow {
    protocol = "tcp"
    ports    = ["9292", "4500"]
  }

  source_service_accounts = [
    var.lb_svc_acct,
  ]

  target_service_accounts = [
    google_service_account.blc[0].email,
  ]
}

resource "google_compute_firewall" "blc-prom" {
  name    = "${var.name}-${var.net}-prometheus-access-${var.env}"
  network = data.google_compute_network.blc.self_link
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
    google_service_account.blc[0].email,
  ]
}

