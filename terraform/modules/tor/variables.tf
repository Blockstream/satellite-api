variable "boot_image" {
  type    = string
  default = "cos-cloud/cos-stable"
}

variable "region" {
  type = string
}

variable "project" {
  type = string
}

variable "name" {
  type = string
}

variable "network" {
  type    = string
  default = "default"
}

variable "zone" {
  type = string
}

variable "instance_type" {
  type = string
}

variable "tor_lb" {
  type = string
}

variable "onion_host" {
  type = string
}

variable "create_resources" {
  type = string
}

variable "prom_service_acct" {
  type = string
}

variable "tor_docker" {
  type = string
}

variable "node_exporter_docker" {
  type = string
}

variable "gcloud_docker" {
  type = string
}

