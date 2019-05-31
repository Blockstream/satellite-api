data "terraform_remote_state" "blc-mainnet" {
  backend = "gcs"

  config = {
    bucket = "tf-state-satellite-api"
    prefix = "terraform/state"
  }

  workspace = "prod"
}

data "terraform_remote_state" "blc-testnet" {
  backend = "gcs"

  config = {
    bucket = "tf-state-satellite-api"
    prefix = "terraform/state"
  }

  workspace = "testnet-prod"
}

