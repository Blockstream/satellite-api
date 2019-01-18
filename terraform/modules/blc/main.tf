# Instance group
resource "google_compute_instance_group_manager" "blc" {
  name  = "${var.name}-ig-${var.env}"
  count = "${var.create_resources}"

  base_instance_name = "${var.name}-ig-${var.env}-${count.index}"
  instance_template  = "${google_compute_instance_template.blc.self_link}"
  zone               = "${var.zone}"
  target_size        = 1
  update_strategy    = "ROLLING_UPDATE"

  rolling_update_policy {
    type                  = "PROACTIVE"
    minimal_action        = "REPLACE"
    max_surge_fixed       = 0
    max_unavailable_fixed = 1
    min_ready_sec         = 60
  }
}

resource "google_compute_disk" "blc" {
  name  = "${var.name}-data-${var.env}"
  type  = "pd-standard"
  image = "${data.google_compute_image.blc.self_link}"
  zone  = "${var.zone}"
  count = "${var.create_resources}"

  lifecycle {
    prevent_destroy = true
    ignore_changes  = ["image"]
  }
}

# Instance template
resource "google_compute_instance_template" "blc" {
  name_prefix  = "${var.name}-${var.env}-template-"
  description  = "This template is used to create ${var.name} ${var.env} instances."
  machine_type = "${var.instance_type}"
  region       = "${var.region}"
  count        = "${var.create_resources}"

  labels {
    type = "lightning-app"
    name = "${var.name}"
  }

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
  }

  disk {
    source_image = "${var.boot_image}"
    disk_type    = "pd-ssd"
    auto_delete  = true
    boot         = true
  }

  disk {
    source      = "${google_compute_disk.blc.name}"
    auto_delete = false
    device_name = "data"
  }

  network_interface {
    network = "${data.google_compute_network.blc.self_link}"

    access_config {
      nat_ip = "${google_compute_address.blc.address}"
    }
  }

  metadata {
    google-logging-enabled = "true"
    user-data              = "${data.template_cloudinit_config.blc.rendered}"
  }

  service_account {
    email  = "${google_service_account.blc.email}"
    scopes = ["compute-ro", "storage-ro"]
  }

  lifecycle {
    create_before_destroy = true
  }
}
