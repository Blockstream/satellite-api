resource "google_compute_health_check" "tor" {
  name               = "${var.name}-health-check"
  timeout_sec        = 5
  check_interval_sec = 10

  count = "${var.create_resources}"

  tcp_health_check {
    port = "9050"
  }
}

resource "google_compute_region_instance_group_manager" "tor" {
  name   = "${var.name}-ig"
  count  = "${var.create_resources}"
  region = "${var.region}"

  base_instance_name = "${var.name}"
  instance_template  = "${google_compute_instance_template.tor.self_link}"
  target_size        = 1
}

resource "google_compute_instance_template" "tor" {
  name_prefix  = "${var.name}-template-"
  description  = "This template is used to create ${var.name} instances."
  machine_type = "${var.tor_instance_type}"
  count        = "${var.create_resources}"

  labels {
    type    = "tor"
    name    = "${var.name}"
    network = "${var.network}"
  }

  disk {
    source_image = "${var.boot_image}"
    boot         = true
    auto_delete  = true
    disk_type    = "pd-ssd"
    device_name  = "boot"
    disk_size_gb = "20"
  }

  network_interface {
    network = "${data.google_compute_network.default.self_link}"

    access_config {}
  }

  metadata {
    google-logging-enabled = "true"
    "user-data"            = "${data.template_cloudinit_config.tor.rendered}"
  }

  service_account {
    email = "${google_service_account.tor.email}"

    scopes = [
      "https://www.googleapis.com/auth/cloudkms",
      "compute-ro",
      "storage-ro",
    ]
  }

  lifecycle {
    create_before_destroy = true
  }
}