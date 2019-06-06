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
      env            = ""
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

variable "ssl_cert" {
  type    = string
  default = ""
}

variable "rpcuser" {
  type    = string
  default = ""
}

variable "rpcpass" {
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
  default = 15
}

variable "prom_service_acct" {
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

# Overwritten by CI
variable "ionosphere_docker" {
  type    = string
  default = ""
}

variable "ionosphere_sse_docker" {
  type    = string
  default = ""
}

variable "public_bucket_url" {
  type    = string
  default = ""
}

variable "letsencrypt_email" {
  type    = string
  default = ""
}

# Less frequently updated images
variable "bitcoin_docker" {
  type    = string
  default = "blockstream/bitcoind@sha256:91ba0790a0080a99a529e73ef9b14e2d6cf0a30f81d54bfa3729bb47b105b36c"
}

variable "lightning_docker" {
  type    = string
  default = "blockstream/lightningd@sha256:b577dcb8d00ec4bc340884a26f5dfffb7be25dcc4ece48b7e465b3238944ec2c"
}

variable "charge_docker" {
  type    = string
  default = "blockstream/charged@sha256:0d49c1202b8b718b5a93f7e82509d3d724f9d18ff6c14376347f67866ac47ff8"
}

variable "tor_docker" {
  type    = string
  default = "blockstream/tor@sha256:f4d1373cde79fd79b467d2d6da88e37b0da137924bc10ae2d51a83c686c2c125"
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
  default = "google/cloud-sdk@sha256:78e68a98c5d6aa36eca45099bae38a1544a1688fd16b506fb914a29fdf6e4afa"
}

variable "certbot_docker" {
  type    = string
  default = "blockstream/certbot-gcs@sha256:516ba43a03f558c73cd3807dc2b31a3ad123205dd53682a5da70396b75b53881"
}
