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
  workspace = "gossip"

  config = {
    bucket = "terraform-bs-source"
    prefix = "satellite-api-reduced-server"
  }
}

data "terraform_remote_state" "auth-prod" {
  backend   = "gcs"
  workspace = "auth"

  config = {
    bucket = "terraform-bs-source"
    prefix = "satellite-api-reduced-server"
  }
}

data "terraform_remote_state" "btc-src-prod" {
  backend   = "gcs"
  workspace = "btc_src"

  config = {
    bucket = "terraform-bs-source"
    prefix = "satellite-api-reduced-server"
  }
}

