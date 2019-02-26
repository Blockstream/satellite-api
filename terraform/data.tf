data "terraform_remote_state" "blc-prod" {
  backend = "gcs"

  config {
    bucket  = "tf-state-satellite-api"
    prefix  = "terraform/state"
    project = "satellite-api"
  }

  workspace = "prod"
}
