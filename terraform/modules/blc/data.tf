data "google_compute_network" "blc" {
  name = "default"
}

data "google_compute_image" "blc" {
  family  = "satapi-data-${var.env}"
  project = "${var.project}"
  count   = "${var.create_resources}"
}

data "template_file" "blc" {
  template = "${file("${path.module}/cloud-init/blc.yaml")}"
  count    = "${var.create_resources}"

  vars {
    rpcuser               = "${var.rpcuser}"
    rpcpass               = "${var.rpcpass}"
    rpcport               = "${var.net == "testnet" ? "18332" : "8332"}"
    bitcoin_cmd           = "bitcoind ${var.net == "testnet" ? "-testnet" : ""} -printtoconsole"
    lightning_cmd         = "lightningd ${var.net == "testnet" ? "--testnet" : "--mainnet"} --conf=/root/.lightning/lightning.conf --plugin-dir=/usr/local/bin/plugins"
    charge_cmd            = "charged -d /data/charge.db -l /root/.lightning"
    announce_addr         = "${google_compute_address.blc.address}"
    lightning_port        = 9735
    bitcoin_docker        = "${var.bitcoin_docker}"
    lightning_docker      = "${var.lightning_docker}"
    charge_docker         = "${var.charge_docker}"
    redis_port            = 6379
    ionosphere_docker     = "${var.ionosphere_docker}"
    ionosphere_sse_docker = "${var.ionosphere_sse_docker}"
    node_exporter_docker  = "${var.node_exporter_docker}"
    opsgenie_key          = "${var.opsgenie_key}"
    host                  = "${var.host[0]}"
    space_host            = "${var.host[1]}"
  }
}

data "template_cloudinit_config" "blc" {
  gzip          = false
  base64_encode = false
  count         = "${var.create_resources}"

  part {
    content_type = "text/cloud-config"
    content      = "${data.template_file.blc.rendered}"
  }
}
