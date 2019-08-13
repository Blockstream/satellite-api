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
    charge_token          = var.charge_token
    net                   = var.net
    lightning_cmd         = "lightningd ${var.net == "testnet" ? "--testnet" : "--mainnet"} --conf=/root/.lightning/lightning.conf --plugin-dir=/usr/local/bin/plugins"
    charge_cmd            = "charged -d /data/charge.db -l /root/.lightning"
    announce_addr         = google_compute_address.blc[0].address
    lightning_port        = 9735
    lightning_docker      = var.lightning_docker
    charge_docker         = var.charge_docker
    redis_port            = 6379
    ionosphere_docker     = var.ionosphere_docker
    ionosphere_sse_docker = var.ionosphere_sse_docker
    node_exporter_docker  = var.node_exporter_docker
    postgres_docker       = var.postgres_docker
    autossh_docker        = var.autossh_docker
    certbot_docker        = var.certbot_docker
    pguser                = var.pguser
    pgpass                = var.pgpass
    opsgenie_key          = var.opsgenie_key
    k8s_autossh_lb        = var.k8s_autossh_lb
    rpcpass               = var.rpcpass
    k8s_autossh_ssh_port  = "${var.net == "testnet" ? "2222" : "2223"}"
    k8s_autossh_btc_port  = "${var.net == "testnet" ? "18332" : "8332"}"
    cert_bucket           = var.cert_bucket
    ssh_key_net           = var.ssh_key_net
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
