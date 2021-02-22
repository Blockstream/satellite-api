resource "google_compute_region_autoscaler" "satapi-lb" {
  name     = "${var.name}-autoscaler-${var.env}"
  target   = google_compute_region_instance_group_manager.satapi-lb[0].self_link
  region   = var.region
  project  = var.project
  provider = google
  count    = var.create_resources

  autoscaling_policy {
    max_replicas    = 2
    min_replicas    = 1
    cooldown_period = 60

    cpu_utilization {
      target = 0.8
    }
  }
}

# Instance group & template
resource "google_compute_region_instance_group_manager" "satapi-lb" {
  name         = "${var.name}-ig-${var.env}"
  target_pools = [var.target_pool]
  project      = var.project
  provider     = google-beta
  count        = var.create_resources

  base_instance_name = "${var.name}-ig-${var.env}"
  region             = var.region
  target_size        = 1

  version {
    name              = "original"
    instance_template = google_compute_instance_template.satapi-lb[0].self_link
  }

  update_policy {
    type                  = "OPPORTUNISTIC"
    minimal_action        = "REPLACE"
    max_surge_fixed       = 3
    max_unavailable_fixed = 0
    min_ready_sec         = 60
  }
}

resource "google_compute_instance_template" "satapi-lb" {
  name_prefix  = "${var.name}-${var.env}-tmpl-"
  description  = "This template is used to create ${var.name} ${var.env} instances."
  machine_type = var.instance_type
  region       = var.region
  count        = var.create_resources
  project      = var.project

  labels = {
    type = "lightning-app"
    name = var.name
  }

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
  }

  disk {
    source_image = "cos-cloud/cos-stable"
    disk_type    = "pd-standard"
    auto_delete  = true
    boot         = true
    disk_size_gb = 20
  }

  network_interface {
    network = data.google_compute_network.satapi-lb.self_link
    network_ip = google_compute_address.satapi-lb-internal[0].address
    access_config {}
  }

  metadata = {
    google-logging-enabled = "true"
    user-data              = data.template_cloudinit_config.satapi-lb[0].rendered
  }

  service_account {
    email  = google_service_account.satapi-lb[0].email
    scopes = ["compute-ro", "storage-rw"]
  }

  lifecycle {
    create_before_destroy = true
  }
}
