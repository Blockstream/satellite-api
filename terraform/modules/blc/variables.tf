variable "project" {
  type    = string
  default = "satellite-api"
}

variable "boot_image" {
  type    = string
  default = "cos-cloud/cos-stable"
}

variable "create_resources" {
  type = string
}

variable "charge_token" {
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

variable "net" {
  type = string
}

variable "timeout" {
  type = string
}

variable "opsgenie_key" {
  type = string
}

variable "prom_service_acct" {
  type = string
}

variable "lb_svc_acct" {
  type = string
}

variable "pguser" {
  type = string
}

variable "pgpass" {
  type = string
}

variable "k8s_autossh_lb" {
  type = string
}

variable "rpcpass" {
  type = string
}

variable "cert_bucket" {
  type = string
}

variable "ssh_key_net" {
  type = string
}

variable "charge_docker" {
  type = string
}

variable "lightning_docker" {
  type = string
}

variable "ionosphere_docker" {
  type = string
}

variable "ionosphere_sse_docker" {
  type = string
}

variable "node_exporter_docker" {
  type = string
}

variable "postgres_docker" {
  type = string
}

variable "autossh_docker" {
  type = string
}

variable "certbot_docker" {
  type = string
}