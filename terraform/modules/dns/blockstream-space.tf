resource "google_dns_managed_zone" "blockstream-space" {
  name        = "blockstream-space"
  dns_name    = "blockstream.space."
  description = "A long time ago, in a galaxy far, far away... P.S. Don't edit directly in Gcloud, but rather in the Satellite API repo (Otherwise, things break and Chase gets really mad)."
  project     = "${var.project}"
  count       = "${var.create_resources}"

  labels = {
    managed-by = "terraform"
  }
}

resource "google_dns_record_set" "a-satellite" {
  name         = "${google_dns_managed_zone.blockstream-space.dns_name}"
  managed_zone = "${google_dns_managed_zone.blockstream-space.name}"
  type         = "A"
  ttl          = 300
  count        = "${var.create_resources}"

  rrdatas = ["${var.satellite_lb}"]
}

resource "google_dns_record_set" "a-satellite-api" {
  name         = "api.${google_dns_managed_zone.blockstream-space.dns_name}"
  managed_zone = "${google_dns_managed_zone.blockstream-space.name}"
  type         = "A"
  ttl          = 300
  count        = "${var.create_resources}"

  rrdatas = ["${var.satellite_api_lb}"]
}

resource "google_dns_record_set" "a-satellite-api-staging" {
  name         = "staging-api.${google_dns_managed_zone.blockstream-space.dns_name}"
  managed_zone = "${google_dns_managed_zone.blockstream-space.name}"
  type         = "A"
  ttl          = 300
  count        = "${var.create_resources}"

  rrdatas = ["${var.satellite_api_lb_staging}"]
}
