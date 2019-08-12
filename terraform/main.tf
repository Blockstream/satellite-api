terraform {
  required_version = "> 0.11.0"

  backend "gcs" {
    bucket = "terraform-bs-source"
    prefix = "satellite-api"
  }
}

provider "google" {
  project = "var.project"
}

provider "google-beta" {
  project = "var.project"
}

module "blc-mainnet" {
  source = "./modules/blc"

  project               = var.project
  name                  = "satellite-api"
  network               = "default"
  bitcoin_docker        = var.bitcoin_docker
  lightning_docker      = var.lightning_docker
  charge_docker         = var.charge_docker
  ionosphere_docker     = var.ionosphere_docker
  ionosphere_sse_docker = var.ionosphere_sse_docker
  node_exporter_docker  = var.node_exporter_docker
  postgres_docker       = var.postgres_docker
  net                   = "mainnet"
  env                   = local.env
  lb_svc_acct           = module.lb.lb_svc_acct
  cert_bucket           = module.lb.lb_cert_bucket

  create_resources = local.create_mainnet

  # CI vars
  region            = var.region
  zone              = var.zone
  instance_type     = var.instance_type[0]
  timeout           = var.timeout
  prom_service_acct = var.prom_service_acct
  opsgenie_key      = var.opsgenie_key
  rpcuser           = var.rpcuser
  rpcpass           = var.rpcpass
  pguser            = var.pguser
  pgpass            = var.pgpass
}

module "blc-testnet" {
  source = "./modules/blc"

  project               = var.project
  name                  = "satellite-api"
  network               = "default"
  bitcoin_docker        = var.bitcoin_docker
  lightning_docker      = var.lightning_docker
  charge_docker         = var.charge_docker
  ionosphere_docker     = var.ionosphere_docker
  ionosphere_sse_docker = var.ionosphere_sse_docker
  node_exporter_docker  = var.node_exporter_docker
  postgres_docker       = var.postgres_docker
  net                   = "testnet"
  env                   = local.env
  cert_bucket           = "" #data.terraform_remote_state.blc-mainnet.outputs.lb_cert_bucket

  create_resources = local.create_testnet

  # CI vars
  region            = var.region
  zone              = var.zone
  instance_type     = var.instance_type[0]
  timeout           = var.timeout
  prom_service_acct = var.prom_service_acct
  opsgenie_key      = var.opsgenie_key
  rpcuser           = var.rpcuser
  rpcpass           = var.rpcpass
  lb_svc_acct       = var.lb_svc_acct
  pguser            = var.pguser
  pgpass            = var.pgpass
}

module "lb" {
  source = "./modules/lb"

  project              = var.project
  name                 = "satellite-api-lb"
  network              = "default"
  certbot_docker       = var.certbot_docker
  node_exporter_docker = var.node_exporter_docker
  env                  = local.env
  internal_ip_mainnet  = module.blc-mainnet.internal_ip
  internal_ip_testnet  = data.terraform_remote_state.blc-testnet.outputs.blc_internal_ip_testnet
  target_pool          = google_compute_target_pool.lb-pool[0].self_link
  health_check         = google_compute_http_health_check.lb-health[0].self_link

  create_resources = local.create_mainnet

  # CI vars
  region            = var.region
  zone              = var.zone
  instance_type     = var.instance_type[1]
  host              = var.host
  timeout           = var.timeout
  prom_service_acct = var.prom_service_acct
  letsencrypt_email = var.letsencrypt_email
  public_bucket_url = var.public_bucket_url
}

module "tor" {
  source = "./modules/tor"

  project              = var.project
  network              = "default"
  name                 = "satapi-tor"
  gcloud_docker        = var.gcloud_docker
  tor_docker           = var.tor_docker
  node_exporter_docker = var.node_exporter_docker
  kms_key              = element(concat(google_kms_crypto_key.tor-crypto-key.*.name, [""]), 0)
  kms_key_ring         = element(concat(google_kms_key_ring.tor-key-ring.*.name, [""]), 0)
  kms_key_link = element(
    concat(google_kms_crypto_key.tor-crypto-key.*.self_link, [""]),
    0,
  )
  tor_lb = element(
    concat(google_compute_global_address.tor-lb.*.address, [""]),
    0,
  )

  create_resources = local.create_misc

  # CI vars
  region            = var.region
  zone              = var.zone
  instance_type     = var.instance_type[1]
  onion_host        = var.onion_host
  prom_service_acct = var.prom_service_acct
}

module "prometheus" {
  source = "./modules/prometheus"

  project              = var.project
  network              = "default"
  name                 = "satapi-prometheus"
  prom_docker          = var.prom_docker
  node_exporter_docker = var.node_exporter_docker

  create_resources = local.create_misc

  # CI vars
  region                 = var.region
  zone                   = var.zone
  instance_type          = var.instance_type[2]
  prom_allowed_source_ip = var.prom_allowed_source_ip
  opsgenie_key           = var.opsgenie_key
  prom_service_acct      = var.prom_service_acct
}

module "dns" {
  source = "./modules/dns"

  project = var.project

  create_resources = local.create_misc

  # CI vars
  satellite_lb             = var.satellite_lb
  satellite_api_lb         = var.satellite_api_lb
  satellite_api_lb_staging = var.satellite_api_lb_staging
}

