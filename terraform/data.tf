data "terraform_remote_state" "lightning-store-prod" {
  backend = "gcs"

  config {
    bucket  = "tf-state-lightning-store"
    prefix  = "terraform/state"
    project = "blockstream-store"
  }

  workspace = "production"

  defaults {
    prometheus_service_account = "${var.prom_service_acct}"
  }
}

data "terraform_remote_state" "blc-prod" {
  backend = "gcs"

  config {
    bucket  = "tf-state-satellite-api"
    prefix  = "terraform/state"
    project = "satellite-api"
  }

  workspace = "prod"
}
