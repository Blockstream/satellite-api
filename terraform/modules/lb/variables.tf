variable "project" {
  type    = string
  default = "satellite-api"
}

variable "create_resources" {
  type = string
}

variable "env" {
  type = string
}

variable "name" {
  type = string
}

variable "network" {
  type = string
}

variable "region" {
  type = string
}

variable "zone" {
  type = string
}

variable "instance_type" {
  type = string
}

variable "host" {
  type = string
}

variable "timeout" {
  type = string
}

variable "public_bucket_url" {
  type = string
}

variable "letsencrypt_email" {
  type = string
}

variable "internal_ip_mainnet" {
  type = string
}

variable "internal_ip_testnet" {
  type = string
}

variable "health_check" {
  type = string
}

variable "prom_service_acct" {
  type = string
}

variable "target_pool" {
  type = string
}

variable "station1" {
  type = string
}

variable "station2" {
  type = string
}

variable "station3" {
  type = string
}

variable "node_exporter_docker" {
  type = string
}

variable "certbot_docker" {
  type = string
}