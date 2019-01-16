terraform {
  required_version = "> 0.11.0"

  backend "gcs" {
    bucket  = "tf-state-ionosphere"
    prefix  = "terraform/state"
    project = "blockstream-store"
  }
}

data "terraform_remote_state" "lightning-store-prod" {
  backend = "gcs"

  config {
    bucket  = "tf-state-lightning-store"
    prefix  = "terraform/state"
    project = "blockstream-store"
  }

  workspace = "staging"

  defaults {
    prometheus_service_account = "${var.prom_service_acct}"
  }
}

provider "google" {
  project = "${var.project}"
}

module "blc" {
  source = "modules/blc"

  project               = "${var.project}"
  name                  = "satellite-api"
  network               = "default"
  bitcoin_docker        = "${var.bitcoin_docker}"
  lightning_docker      = "${var.lightning_docker}"
  charge_docker         = "${var.charge_docker}"
  ionosphere_docker     = "${var.ionosphere_docker}"
  ionosphere_sse_docker = "${var.ionosphere_sse_docker}"
  node_exporter_docker  = "${var.node_exporter_docker}"
  net                   = "testnet"
  env                   = "${local.env}"

  # CI vars
  region            = "${var.region}"
  zone              = "${var.zone}"
  instance_type     = "${var.instance_type}"
  host              = "${var.host}"
  ssl_cert          = "${var.ssl_cert}"
  timeout           = "${var.timeout}"
  prom_service_acct = "${data.terraform_remote_state.lightning-store-prod.prometheus_service_account}"
  opsgenie_key      = "${var.opsgenie_key}"
  rpcuser           = "${var.rpcuser}"
  rpcpass           = "${var.rpcpass}"
}
