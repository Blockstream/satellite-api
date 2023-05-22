resource "google_service_account" "api_server_ci" {
  project      = var.project
  account_id   = "satellite-api-tf-ci"
  display_name = "satellite-api-tf-ci"
  description  = "Terraform/CI"
  count        = local.create_misc
}

resource "google_project_iam_member" "api_server_ci" {
  project = var.project
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.api_server_ci[0].email}"
  count   = local.create_misc
}

resource "google_project_iam_member" "api_server_ci_storageadm" {
  project = var.project
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.api_server_ci[0].email}"
  count   = local.create_misc
}
