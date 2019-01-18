resource "google_service_account" "blc" {
  account_id   = "${var.name}-${var.env}"
  display_name = "${var.name}-${var.env}"
  count        = "${var.create_resources}"
}

resource "google_project_iam_member" "blc" {
  project = "${var.project}"
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.blc.email}"
  count   = "${var.create_resources}"
}
