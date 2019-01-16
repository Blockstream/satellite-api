locals {
  context_variables = {
    "staging" = {
      env = "staging"
    }

    "prod" = {
      env = "prod"
    }
  }

  env = "${lookup(local.context_variables[terraform.workspace], "env")}"
}

variable "project" {
  type    = "string"
  default = "blockstream-store"
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
