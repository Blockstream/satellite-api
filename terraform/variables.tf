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
    "testnet-staging" = {
      env            = "staging"
      create_mainnet = 0
      create_testnet = 1
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
  type    = string
  default = ""
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

variable "internal_ip_mainnet" {
  type    = string
  default = ""
}

variable "internal_ip_testnet" {
  type    = string
  default = ""
}

variable "internal_ip_gossip" {
  type    = string
  default = ""
}

variable "internal_ip_auth" {
  type    = string
  default = ""
}

variable "internal_ip_btc_src" {
  type    = string
  default = ""
}

variable "health_check" {
  type    = string
  default = ""
}

variable "pguser" {
  type    = string
  default = ""
}

variable "pgpass" {
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
  type = string
  default = ""
}

variable "station2" {
  type = string
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
  default = "blockstream/lightningd@sha256:baa37ddc2019af21c187052fe6b457d7c604de512c209fc494efebecfb7a24ab"
}

variable "charge_docker" {
  type    = string
  default = "blockstream/charged@sha256:bcc5f91643f03bd97601471d335f133d75455d096054f01c15d332138a55a49c"
}

variable "tor_docker" {
  type    = string
  default = "blockstream/tor@sha256:46594b0a84f7503de70078652e7bd94f6152b7976d11779ad9f143f02508284c"
}

variable "node_exporter_docker" {
  type    = string
  default = "prom/node-exporter@sha256:55302581333c43d540db0e144cf9e7735423117a733cdec27716d87254221086"
}

variable "prom_docker" {
  type    = string
  default = "blockstream/prometheus@sha256:cab8c2359ab187aa6c9e9c7fcfcc3060b62742417030a77862c747e091d3c6d6"
}

variable "gcloud_docker" {
  type    = string
  default = "google/cloud-sdk@sha256:ce81a5731934dabf2a402412a6cd4ef5733581302053007ba7de261513bff9bd"
}

variable "certbot_docker" {
  type    = string
  default = "blockstream/certbot-gcs@sha256:fc5d7cb31bcf04169f37cbebd74c3bde49651f79e54e1ff3c3eaf6ec47b9f6d0"
}

variable "postgres_docker" {
  type    = string
  default = "postgres@sha256:077793cc0ed31fd0568ce468d85d0843b8dea37c9ef74eb81b4ccf0fe9539e2e"
}

variable "autossh_docker" {
  type    = string
  default = "blockstream/autossh@sha256:5e30a60d6ef17aeafdde63bb859238e132fadef174af4092a435bc7325430ebd"
}
