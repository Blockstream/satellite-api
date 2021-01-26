data "google_compute_network" "satapi-lb" {
  name    = "default"
  project = var.project
}

data "template_file" "satapi-lb" {
  template = file("${path.module}/cloud-init/lb.yaml")
  count    = var.create_resources

  vars = {
    mainnet_ip           = var.internal_ip_mainnet
    testnet_ip           = var.internal_ip_testnet
    gossip_ip            = var.internal_ip_gossip
    auth_ip              = var.internal_ip_auth
    btc_src_ip           = var.internal_ip_btc_src
    certbot_docker       = var.certbot_docker
    node_exporter_docker = var.node_exporter_docker
    host                 = var.host
    public_bucket_url    = "${var.public_bucket_url}-${var.env}"
    public_bucket        = replace(google_storage_bucket.satapi-lb-public[count.index].url, "gs://", "")
    private_bucket       = replace(google_storage_bucket.satapi-lb-private[count.index].url, "gs://", "")
    letsencrypt_email    = var.letsencrypt_email
    station1             = var.station1
    station2             = var.station2
  }
}

data "template_cloudinit_config" "satapi-lb" {
  gzip          = false
  base64_encode = false
  count         = var.create_resources

  part {
    content_type = "text/cloud-config"
    content      = data.template_file.satapi-lb[0].rendered
  }
}
