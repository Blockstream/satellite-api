# External and internal static IPs
resource "google_compute_address" "blc" {
  name    = "${var.name}-${var.net}-external-ip-${var.env}"
  project = var.project
  region  = var.region
  count   = var.create_resources
}

resource "google_compute_address" "blc-internal" {
  name         = "${var.name}-${var.net}-internal-ip-${var.env}"
  address_type = "INTERNAL"
  project      = var.project
  region       = var.region
  count        = var.create_resources
}
