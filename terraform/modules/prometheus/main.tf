resource "google_compute_disk" "prometheus-data" {
  name    = "${var.name}-data-disk"
  project = var.project
  type    = "pd-standard"
  zone    = var.zone
  size    = "50"
  count   = var.create_resources
}

resource "google_compute_address" "prometheus-address" {
  name    = "${var.name}-address"
  project = var.project
  region  = var.region
  count   = var.create_resources
}

resource "google_compute_address" "prometheus-internal-address" {
  name         = "${var.name}-internal-address"
  project      = var.project
  region       = var.region
  address_type = "INTERNAL"
  count        = var.create_resources
}

locals {
  service_account = terraform.workspace == "misc" ? element(concat(google_service_account.prometheus.*.email, [""]), 0) : var.prom_service_acct
}

resource "google_compute_instance" "prometheus-server" {
  name                      = var.name
  machine_type              = var.instance_type
  zone                      = var.zone
  project                   = var.project
  allow_stopping_for_update = true
  count                     = var.create_resources

  labels = {
    type    = "prometheus"
    name    = var.name
    network = var.network
  }

  service_account {
    email = local.service_account

    scopes = [
      "https://www.googleapis.com/auth/compute.readonly",
      "https://www.googleapis.com/auth/devstorage.read_only",
      "https://www.googleapis.com/auth/pubsub",
    ]
  }

  boot_disk {
    initialize_params {
      size  = "20"
      image = var.boot_image
    }
  }

  attached_disk {
    source      = element(google_compute_disk.prometheus-data.*.name, count.index)
    device_name = "data"
  }

  network_interface {
    network = data.google_compute_network.default[0].self_link
    network_ip = element(
      google_compute_address.prometheus-internal-address.*.address,
      count.index,
    )

    access_config {
      nat_ip = element(
        google_compute_address.prometheus-address.*.address,
        count.index,
      )
    }
  }

  metadata = {
    user-data = data.template_cloudinit_config.prometheus[0].rendered
  }
}

