locals {
  context_variables = {
    "staging" = {
      env            = "staging"
      create_mainnet = 1
      create_testnet = 0
      create_misc    = 0
    }
    "prod" = {
      env            = "prod"
      create_mainnet = 1
      create_testnet = 0
      create_misc    = 0
    }
    "testnet-prod" = {
      env            = "prod"
      create_mainnet = 0
      create_testnet = 1
      create_misc    = 0
    }
    "misc" = {
      env            = "prod"
      create_mainnet = 0
      create_testnet = 0
      create_misc    = 1
    }
  }

  env            = local.context_variables[terraform.workspace]["env"]
  create_mainnet = local.context_variables[terraform.workspace]["create_mainnet"]
  create_testnet = local.context_variables[terraform.workspace]["create_testnet"]
  create_misc    = local.context_variables[terraform.workspace]["create_misc"]
}

variable "project" {
  type    = string
  default = "satellite-api"
}

variable "name" {
  type    = string
  default = "satapi-tor"
}

variable "create_resources" {
  type    = string
  default = ""
}

variable "target_pool" {
  type    = string
  default = ""
}

variable "charge_token" {
  type    = string
  default = ""
}

variable "host" {
  type    = string
  default = ""
}

variable "onion_host" {
  type    = string
  default = ""
}

variable "region" {
  type    = string
  default = ""
}

variable "zone" {
  type    = string
  default = ""
}

variable "instance_type" {
  type    = list(string)
  default = ["", "", ""]
}

variable "timeout" {
  type    = string
  default = 7200
}

variable "prom_service_acct" {
  type    = string
  default = ""
}

variable "lb_svc_acct" {
  type    = string
  default = ""
}

variable "prom_allowed_source_ip" {
  type    = list(any)
  default = []
}

variable "opsgenie_key" {
  type    = string
  default = ""
}

variable "satellite_lb" {
  type    = string
  default = ""
}

variable "satellite_api_lb" {
  type    = string
  default = ""
}

variable "satellite_api_lb_staging" {
  type    = string
  default = ""
}

variable "blocksat_monitoring" {
  type    = string
  default = ""
}

variable "internal_ip_mainnet" {
  type    = string
  default = ""
}

variable "internal_ip_testnet" {
  type    = string
  default = ""
}

variable "health_check" {
  type    = string
  default = ""
}

variable "k8s_autossh_lb" {
  type    = string
  default = ""
}

variable "rpcpass" {
  type    = string
  default = ""
}

variable "ssh_key_net" {
  type    = string
  default = ""
}

variable "lightning_cmd" {
  type    = string
  default = ""
}

# Overwritten by CI
variable "public_bucket_url" {
  type    = string
  default = ""
}

variable "private_bucket" {
  type    = string
  default = ""
}

variable "letsencrypt_email" {
  type    = string
  default = ""
}

variable "station1" {
  type    = string
  default = ""
}

variable "station2" {
  type    = string
  default = ""
}

variable "ionosphere_docker" {
  type    = string
  default = ""
}

variable "ionosphere_sse_docker" {
  type    = string
  default = ""
}

# Less frequently updated images
variable "lightning_docker" {
  type    = string
  default = "blockstream/lightningd:v23.02.2"
}

variable "charge_docker" {
  type    = string
  default = "blockstream/charged:v0.4.23"
}

variable "tor_docker" {
  type    = string
  default = "blockstream/tor:0.4.6.8"
}

variable "node_exporter_docker" {
  type    = string
  default = "prom/node-exporter:v1.1.2"
}

variable "prom_docker" {
  type    = string
  default = "prom/prometheus:v2.29.1"
}

variable "gcloud_docker" {
  type    = string
  default = "google/cloud-sdk@sha256:ce81a5731934dabf2a402412a6cd4ef5733581302053007ba7de261513bff9bd"
}

variable "certbot_docker" {
  type    = string
  default = "blockstream/certbot-gcs@sha256:fc5d7cb31bcf04169f37cbebd74c3bde49651f79e54e1ff3c3eaf6ec47b9f6d0"
}

variable "autossh_docker" {
  type    = string
  default = "blockstream/autossh@sha256:5e30a60d6ef17aeafdde63bb859238e132fadef174af4092a435bc7325430ebd"
}
