terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
    }
    google-beta = {
      source = "hashicorp/google-beta"
    }
  }
  required_version = ">= 0.15"

  backend "gcs" {
    bucket = "terraform-bs-source"
    prefix = "satellite-api"
  }
}

provider "google" {
  project = var.project
}

provider "google-beta" {
  project = var.project
}

module "blc-mainnet" {
  source = "./modules/blc"

  project               = var.project
  name                  = "satellite-api"
  network               = "default"
  lightning_docker      = var.lightning_docker
  charge_docker         = var.charge_docker
  sat_api_docker        = var.sat_api_docker
  sat_api_sse_docker    = var.sat_api_sse_docker
  node_exporter_docker  = var.node_exporter_docker
  autossh_docker        = var.autossh_docker
  certbot_docker        = var.certbot_docker
  net                   = "mainnet"
  env                   = local.env
  lb_svc_acct           = module.lb.lb_svc_acct
  ssh_key_net           = ""
  lightning_cmd         = "--mainnet --conf=/root/.lightning/bitcoin/lightning.conf"

  create_resources = local.create_mainnet

  # CI vars
  region            = var.region
  zone              = var.zone
  instance_type     = var.instance_type[1]
  timeout           = var.timeout
  prom_service_acct = var.prom_service_acct
  rpcpass           = var.rpcpass
  charge_token      = var.charge_token
  k8s_autossh_lb    = var.k8s_autossh_lb
  private_bucket    = var.private_bucket
}

module "blc-testnet" {
  source = "./modules/blc"

  project               = var.project
  name                  = "satellite-api"
  network               = "default"
  lightning_docker      = var.lightning_docker
  charge_docker         = var.charge_docker
  sat_api_docker        = var.sat_api_docker
  sat_api_sse_docker    = var.sat_api_sse_docker
  node_exporter_docker  = var.node_exporter_docker
  autossh_docker        = var.autossh_docker
  certbot_docker        = var.certbot_docker
  net                   = "testnet"
  env                   = local.env
  lb_svc_acct           = length(data.terraform_remote_state.blc-mainnet.outputs) > 1 ? data.terraform_remote_state.blc-mainnet.outputs.lb_svc_acct : ""
  ssh_key_net           = "_testnet"
  lightning_cmd         = "--testnet --conf=/root/.lightning/testnet/lightning.conf"

  create_resources = local.create_testnet

  # CI vars
  region            = var.region
  zone              = var.zone
  instance_type     = var.instance_type[1]
  timeout           = var.timeout
  prom_service_acct = var.prom_service_acct
  rpcpass           = var.rpcpass
  charge_token      = var.charge_token
  k8s_autossh_lb    = var.k8s_autossh_lb
  private_bucket    = var.private_bucket
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
  internal_ip_testnet  = local.env == "staging" ? "127.0.0.1" : data.terraform_remote_state.blc-testnet.outputs.blc_internal_ip_testnet
  # NOTE: There is no testnet server on staging. The IP is set to 127.0.0.1
  # above so that the nginx conf does not see an empty IP and fail.
  target_pool  = length(google_compute_target_pool.lb-pool) > 0 ? google_compute_target_pool.lb-pool[0].self_link : ""
  health_check = length(google_compute_http_health_check.lb-health) > 0 ? google_compute_http_health_check.lb-health[0].self_link : ""

  create_resources = local.create_mainnet

  # CI vars
  region            = var.region
  zone              = var.zone
  instance_type     = var.instance_type[0]
  host              = var.host
  timeout           = var.timeout
  prom_service_acct = var.prom_service_acct
  letsencrypt_email = var.letsencrypt_email
  public_bucket_url = var.public_bucket_url
  station1          = var.station1
  station2          = var.station2
  station3          = var.station3
}

module "tor" {
  source = "./modules/tor"

  project              = var.project
  network              = "default"
  name                 = "satapi-tor"
  gcloud_docker        = var.gcloud_docker
  tor_docker           = var.tor_docker
  node_exporter_docker = var.node_exporter_docker
  tor_lb = element(
    concat(google_compute_global_address.tor-lb.*.address, [""]),
    0,
  )

  create_resources = local.create_misc

  # CI vars
  region            = var.region
  zone              = var.zone
  instance_type     = var.instance_type[0]
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
  instance_type          = var.instance_type[1]
  prom_allowed_source_ip = var.prom_allowed_source_ip
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
  blocksat_monitoring      = var.blocksat_monitoring
}
