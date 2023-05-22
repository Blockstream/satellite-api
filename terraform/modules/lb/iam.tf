resource "google_service_account" "satapi-lb" {
  account_id   = "${var.name}-${var.env}"
  display_name = "${var.name}-${var.env}"
  project      = var.project
  count        = var.create_resources
}

resource "google_project_iam_member" "satapi-lb" {
  project = var.project
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.satapi-lb[0].email}"
  count   = var.create_resources
}

# GCS buckets access for TLS management
locals {
  buckets = var.create_resources == "1" ? {
    public  = google_storage_bucket.satapi-lb-public[0].name
    private = google_storage_bucket.satapi-lb-private[0].name
  } : {}

  roles = {
    objectCreator      = "roles/storage.objectCreator",
    objectViewer       = "roles/storage.objectViewer",
    legacyBucketWriter = "roles/storage.legacyBucketWriter"
  }

  bucket_role_pairs = flatten([
    for b_key, b_name in local.buckets : [
      for r_key, r_value in local.roles : {
        bucket_key = b_key
        bucket     = b_name
        role_key   = r_key
        role       = r_value
      }
    ]
  ])

  bucket_roles = { for br in local.bucket_role_pairs : "${br.bucket_key}_${br.role_key}" => br }
}

resource "google_storage_bucket_iam_member" "satapi_lb_roles" {
  # for_each = local.bucket_roles
  for_each = var.create_resources == "1" ? local.bucket_roles : {}

  bucket = each.value.bucket
  role   = each.value.role
  member = "serviceAccount:${google_service_account.satapi-lb[0].email}"
}
