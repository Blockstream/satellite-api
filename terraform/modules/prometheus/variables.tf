variable "boot_image" {
  type    = string
  default = "cos-cloud/cos-stable"
}

variable "network" {
  type    = string
  default = "default"
}

variable "retention" {
  type    = string
  default = "31d"
}

variable "project" {
  type = string
}

variable "name" {
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

variable "create_resources" {
  type = string
}

variable "prom_service_acct" {
  type = string
}

variable "prom_allowed_source_ip" {
  type = list(any)
}

variable "prom_docker" {
  type = string
}

variable "node_exporter_docker" {
  type = string
}
