resource "google_kms_key_ring" "tor-key-ring" {
  project  = var.project
  name     = "${var.name}-keyring"
  location = var.region
  count    = var.create_resources
}

resource "google_kms_crypto_key" "tor-crypto-key" {
  name     = "${var.name}-crypto-key"
  key_ring = google_kms_key_ring.tor-key-ring[0].id
  count    = var.create_resources
}
