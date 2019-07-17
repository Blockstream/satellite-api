data "google_compute_network" "default" {
  name    = "default"
  project = var.project
}

data "template_file" "tor" {
  template = file("${path.module}/cloud-init/tor.yaml")
  count    = var.create_resources

  vars = {
    tor_lb               = var.tor_lb
    v3_host              = var.onion_host
    v3_pk                = file("${path.module}/v3.pk")
    v3_pubk              = file("${path.module}/v3.pubk")
    tor_docker           = var.tor_docker
    gcloud_docker        = var.gcloud_docker
    node_exporter_docker = var.node_exporter_docker
    kms_key              = var.kms_key
    kms_key_ring         = var.kms_key_ring
    kms_location         = var.region
  }
}

data "template_cloudinit_config" "tor" {
  gzip          = false
  base64_encode = false

  part {
    content_type = "text/cloud-config"
    content      = data.template_file.tor[0].rendered
  }
}

