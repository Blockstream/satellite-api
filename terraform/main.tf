terraform {
  required_version = "> 0.11.0"

  backend "gcs" {
    bucket  = "tf-state-ionosphere"
    prefix  = "terraform/state"
    project = "blockstream-store"
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

  create_resources = "${local.create_satapi}"

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

module "tor" {
  source = "modules/tor"

  project              = "${var.project}"
  network              = "default"
  name                 = "satapi-tor"
  gcloud_docker        = "${var.gcloud_docker}"
  tor_docker           = "${var.tor_docker}"
  node_exporter_docker = "${var.node_exporter_docker}"
  kms_key              = "${element(concat(google_kms_crypto_key.tor-crypto-key.*.name, list("")), 0)}"
  kms_key_ring         = "${element(concat(google_kms_key_ring.tor-key-ring.*.name, list("")), 0)}"
  kms_key_link         = "${element(concat(google_kms_crypto_key.tor-crypto-key.*.self_link, list("")), 0)}"
  tor_lb               = "${element(concat(google_compute_global_address.tor-lb.*.address, list("")), 0)}"

  create_resources = "${local.create_misc}"

  #CI vars
  region            = "${var.region}"
  zone              = "${var.zone}"
  tor_instance_type = "${var.tor_instance_type}"
  onion_host        = "${var.onion_host}"
  prom_service_acct = "${data.terraform_remote_state.lightning-store-prod.prometheus_service_account}"
}
