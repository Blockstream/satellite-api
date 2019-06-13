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

