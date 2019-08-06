# Public bucket (certbot acme-challenge)
resource "google_storage_bucket" "satapi-lb-public" {
  name          = "${var.name}-certbot-${var.env}"
  location      = "US"
  storage_class = "MULTI_REGIONAL"
  project       = var.project
  count         = var.create_resources

  lifecycle {
    ignore_changes = ["name"]
  }
}

resource "google_storage_bucket_acl" "satapi-lb-public-acl" {
  bucket         = google_storage_bucket.satapi-lb-public[count.index].name
  predefined_acl = "publicread"
  count          = var.create_resources
}

# Private bucket (server certs, ssh keys)
resource "google_storage_bucket" "satapi-lb-private" {
  name          = "${var.name}-certs-${var.env}"
  location      = "US"
  storage_class = "MULTI_REGIONAL"
  project       = var.project
  count         = var.create_resources

  lifecycle {
    ignore_changes = ["name"]
  }
}

resource "google_storage_bucket_acl" "satapi-lb-private-acl" {
  bucket         = google_storage_bucket.satapi-lb-private[count.index].name
  predefined_acl = "projectprivate"
  count          = var.create_resources
}
