locals {
  context_variables = {
    "staging" = {
      env             = "staging"
      create_satapi   = 1
      create_misc     = 0
      create_builders = 0
    }

    "prod" = {
      env             = "prod"
      create_satapi   = 1
      create_misc     = 0
      create_builders = 0
    }

    "misc" = {
      env             = ""
      create_satapi   = 0
      create_misc     = 1
      create_builders = 0
    }

    "builders" = {
      env             = ""
      create_satapi   = 0
      create_misc     = 0
      create_builders = 1
    }
  }

  env             = "${lookup(local.context_variables[terraform.workspace], "env")}"
  create_satapi   = "${lookup(local.context_variables[terraform.workspace], "create_satapi")}"
  create_misc     = "${lookup(local.context_variables[terraform.workspace], "create_misc")}"
  create_builders = "${lookup(local.context_variables[terraform.workspace], "create_builders")}"
}

variable "project" {
  type    = "string"
  default = "blockstream-store"
}

variable "name" {
  type    = "string"
  default = "satapi-tor"
}

variable "create_resources" {
  type    = "string"
  default = ""
}

variable "ssl_cert" {
  type    = "string"
  default = ""
}

variable "rpcuser" {
  type    = "string"
  default = ""
}

variable "rpcpass" {
  type    = "string"
  default = ""
}

variable "host" {
  type    = "string"
  default = ""
}

variable "onion_host" {
  type    = "string"
  default = ""
}

variable "region" {
  type    = "string"
  default = ""
}

variable "zone" {
  type    = "string"
  default = ""
}

variable "instance_type" {
  type    = "string"
  default = ""
}

variable "tor_instance_type" {
  type    = "string"
  default = ""
}

variable "timeout" {
  type    = "string"
  default = 15
}

variable "prom_service_acct" {
  type    = "string"
  default = ""
}

variable "opsgenie_key" {
  type    = "string"
  default = ""
}

# Overwritten by CI
variable "ionosphere_docker" {
  type    = "string"
  default = ""
}

variable "ionosphere_sse_docker" {
  type    = "string"
  default = ""
}

# Less frequently updated images
variable "node_exporter_docker" {
  type    = "string"
  default = "prom/node-exporter@sha256:55302581333c43d540db0e144cf9e7735423117a733cdec27716d87254221086"
}

variable "bitcoin_docker" {
  type    = "string"
  default = "us.gcr.io/blockstream-store/bitcoind@sha256:d385d5455000b85b0e2103cdbc69e642c46872b698ff807892ba4c4a40e72ca7"
}

variable "lightning_docker" {
  type    = "string"
  default = "us.gcr.io/blockstream-store/lightningd@sha256:ca00792c25f4af420db94501d37bf8570d642ae21b7fd30792364aa9a617ec87"
}

variable "charge_docker" {
  type    = "string"
  default = "us.gcr.io/blockstream-store/charged@sha256:669893e02a14863f469498a40626e46de3ec67ff2ee4d7443cd56bc6ba3a8f3a"
}

variable "tor_docker" {
  type    = "string"
  default = "blockstream/gcloud-tor@sha256:be56a33b3010ac4c85037899714979bb4eb6c15fe85114bd009501750320617f"
}

variable "gcloud_docker" {
  type    = "string"
  default = "google/cloud-sdk@sha256:b0d0555efef6a566f42fc4f0d89be9e1d74aff4565e27bbd206405f759d3f2b0"
}
