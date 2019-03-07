resource "google_compute_firewall" "blc" {
  name    = "${var.name}-${var.net}-fw-rule-${var.env}"
  network = "${data.google_compute_network.blc.self_link}"
  count   = "${var.create_resources}"

  allow {
    protocol = "tcp"
    ports    = ["18333", "8333", "9735", "80"]
  }

  target_service_accounts = [
    "${google_service_account.blc.email}",
  ]
}

resource "google_compute_firewall" "blc-prom" {
  name    = "${var.name}-${var.net}-prometheus-access-${var.env}"
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
