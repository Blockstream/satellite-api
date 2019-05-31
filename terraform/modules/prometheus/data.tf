data "google_compute_network" "default" {
  name = "default"
  project = var.project
}

data "template_file" "prometheus" {
  template = file("${path.module}/cloud-init/prometheus.yml")

  vars = {
    prom_docker          = var.prom_docker
    node_exporter_docker = var.node_exporter_docker
    retention            = var.retention
    opsgenie_key         = var.opsgenie_key
  }
}

data "template_cloudinit_config" "prometheus" {
  gzip          = false
  base64_encode = false

  part {
    content_type = "text/cloud-config"
    content      = data.template_file.prometheus.rendered
  }
}

