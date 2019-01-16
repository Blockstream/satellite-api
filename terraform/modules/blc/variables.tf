variable "project" {
  type    = "string"
  default = "blockstream-store"
}

variable "boot_image" {
  type    = "string"
  default = "cos-cloud/cos-stable"
}

variable "rpcuser" {
  type    = "string"
  default = ""
}

variable "rpcpass" {
  type    = "string"
  default = ""
}

variable "env" {
  type = "string"
}

variable "name" {
  type = "string"
}

variable "network" {
  type = "string"
}

variable "region" {
  type = "string"
}

variable "zone" {
  type = "string"
}

variable "instance_type" {
  type = "string"
}

variable "net" {
  type = "string"
}

variable "ssl_cert" {
  type = "string"
}

variable "host" {
  type = "string"
}

variable "timeout" {
  type = "string"
}

variable "opsgenie_key" {
  type = "string"
}

variable "prom_service_acct" {
  type = "string"
}

variable "bitcoin_docker" {
  type = "string"
}

variable "charge_docker" {
  type = "string"
}

variable "lightning_docker" {
  type = "string"
}

variable "ionosphere_docker" {
  type = "string"
}

variable "ionosphere_sse_docker" {
  type = "string"
}

variable "node_exporter_docker" {
  type = "string"
}
