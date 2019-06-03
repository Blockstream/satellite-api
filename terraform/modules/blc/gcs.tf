# Public bucket (certbot acme-challenge)
resource "google_storage_bucket" "blc-public" {
  name          = "${var.name}-certbot-${var.env}"
  location      = "US"
  storage_class = "MULTI_REGIONAL"
  count         = var.create_resources

  lifecycle {
    ignore_changes = ["name"]
  }
}

resource "google_storage_bucket_acl" "blc-public-acl" {
  bucket         = replace(google_storage_bucket.blc-public[count.index].url, "gs://", "")
  predefined_acl = "publicread"
  count          = var.create_resources
}

resource "google_storage_bucket_iam_binding" "blc-public-binding" {
  bucket = replace(google_storage_bucket.blc-public[count.index].url, "gs://", "")
  role   = "roles/storage.admin"
  count  = var.create_resources

  members = [
    "serviceAccount:${google_service_account.blc[count.index].email}",
  ]
}

# Private bucket (server certs)
resource "google_storage_bucket" "blc-private" {
  name          = "${var.name}-certs-${var.env}"
  location      = "US"
  storage_class = "MULTI_REGIONAL"
  count         = var.create_resources

  lifecycle {
    ignore_changes = ["name"]
  }
}

resource "google_storage_bucket_iam_binding" "blc-private-binding" {
  bucket = replace(google_storage_bucket.blc-private[count.index].url, "gs://", "")
  role   = "roles/storage.admin"
  count  = var.create_resources

  members = [
    "serviceAccount:${google_service_account.blc[count.index].email}",
  ]
}
