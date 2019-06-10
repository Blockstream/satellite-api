# Public bucket (certbot acme-challenge)
resource "google_storage_bucket" "blc-public" {
  name          = "${var.name}-certbot-${var.env}"
  location      = "US"
  storage_class = "MULTI_REGIONAL"
  project       = var.project
  count         = var.create_resources

  lifecycle {
    ignore_changes = ["name"]
  }
}

resource "google_storage_bucket_acl" "blc-public-acl" {
  bucket         = google_storage_bucket.blc-public[count.index].name
  predefined_acl = "publicread"
  count          = var.create_resources
}

# Private bucket (server certs)
resource "google_storage_bucket" "blc-private" {
  name          = "${var.name}-certs-${var.env}"
  location      = "US"
  storage_class = "MULTI_REGIONAL"
  project       = var.project
  count         = var.create_resources

  lifecycle {
    ignore_changes = ["name"]
  }
}

resource "google_storage_bucket_acl" "blc-private-acl" {
  bucket         = google_storage_bucket.blc-private[count.index].name
  predefined_acl = "projectprivate"
  count          = var.create_resources
}
