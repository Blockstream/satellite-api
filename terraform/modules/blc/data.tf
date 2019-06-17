data "google_compute_network" "blc" {
  name    = "default"
  project = var.project
}

data "google_compute_image" "blc" {
  family  = "satapi-data-${var.net}-${var.env}"
  project = var.project
  count   = var.create_resources
}

data "template_file" "blc" {
  template = file("${path.module}/cloud-init/blc.yaml")
  count    = var.create_resources

  vars = {
    rpcuser               = var.rpcuser
    rpcpass               = var.rpcpass
    net                   = var.net
    bitcoin_cmd           = "bitcoind ${var.net == "testnet" ? "-testnet" : ""} -printtoconsole"
    lightning_cmd         = "lightningd ${var.net == "testnet" ? "--testnet" : "--mainnet"} --conf=/root/.lightning/lightning.conf --plugin-dir=/usr/local/bin/plugins"
    charge_cmd            = "charged -d /data/charge.db -l /root/.lightning"
    announce_addr         = google_compute_address.blc[0].address
    lightning_port        = 9735
    bitcoin_docker        = var.bitcoin_docker
    lightning_docker      = var.lightning_docker
    charge_docker         = var.charge_docker
    redis_port            = 6379
    ionosphere_docker     = var.ionosphere_docker
    ionosphere_sse_docker = var.ionosphere_sse_docker
    node_exporter_docker  = var.node_exporter_docker
    opsgenie_key          = var.opsgenie_key
  }
}

data "template_cloudinit_config" "blc" {
  gzip          = false
  base64_encode = false
  count         = var.create_resources

  part {
    content_type = "text/cloud-config"
    content      = data.template_file.blc[0].rendered
  }
}
