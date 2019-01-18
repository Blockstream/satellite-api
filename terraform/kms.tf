resource "google_kms_key_ring" "tor-key-ring" {
  project  = "${var.project}"
  name     = "${var.name}-keyring"
  location = "${var.region}"

  count = "${local.create_misc}"
}

resource "google_kms_crypto_key" "tor-crypto-key" {
  name     = "${var.name}-crypto-key"
  key_ring = "${google_kms_key_ring.tor-key-ring.id}"

  count = "${local.create_misc}"
}
