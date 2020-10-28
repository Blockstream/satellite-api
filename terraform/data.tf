data "terraform_remote_state" "blc-mainnet" {
  backend   = "gcs"
  workspace = local.env

  config = {
    bucket = "terraform-bs-source"
    prefix = "satellite-api"
  }
}

data "terraform_remote_state" "blc-testnet" {
  backend   = "gcs"
  workspace = "testnet-${local.env}"

  config = {
    bucket = "terraform-bs-source"
    prefix = "satellite-api"
  }
}

data "terraform_remote_state" "gossip-prod" {
  backend   = "gcs"
  workspace = "prod"

  config = {
    bucket = "terraform-bs-source"
    prefix = "satellite-api-gossip"
  }
}
