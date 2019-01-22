resource "google_compute_global_address" "tor-lb" {
  name    = "${var.name}-lb"
  project = "${var.project}"
  count   = "${local.create_misc}"
}

resource "google_compute_global_forwarding_rule" "tor-rule" {
  name        = "${var.name}-forwarding-rule"
  target      = "${google_compute_target_http_proxy.tor-proxy.self_link}"
  port_range  = "80"
  ip_protocol = "TCP"
  ip_address  = "${google_compute_global_address.tor-lb.address}"

  count = "${local.create_misc}"
}

resource "google_compute_target_http_proxy" "tor-proxy" {
  name    = "${var.name}-http-proxy"
  url_map = "${google_compute_url_map.tor-proxy.self_link}"

  count = "${local.create_misc}"
}

resource "google_compute_url_map" "tor-proxy" {
  name            = "${var.name}-urlmap"
  default_service = "${google_compute_backend_bucket.tor_deadhole_backend.self_link}"

  count = "${local.create_misc}"

  host_rule {
    hosts        = ["*"]
    path_matcher = "deadpaths"
  }

  path_matcher {
    name            = "deadpaths"
    default_service = "${google_compute_backend_bucket.tor_deadhole_backend.self_link}"

    path_rule {
      paths   = ["/*"]
      service = "${google_compute_backend_bucket.tor_deadhole_backend.self_link}"
    }
  }

  host_rule {
    hosts        = ["${var.onion_host}"]
    path_matcher = "allpaths"
  }

  path_matcher {
    name            = "allpaths"
    default_service = "${data.terraform_remote_state.blc-prod.blc_backend_service}"

    path_rule {
      paths   = ["/*"]
      service = "${data.terraform_remote_state.blc-prod.blc_backend_service}"
    }
  }

  test {
    service = "${data.terraform_remote_state.blc-prod.blc_backend_service}"
    host    = "${var.onion_host}"
    path    = "/api/queue.html"
  }

  test {
    service = "${google_compute_backend_bucket.tor_deadhole_backend.self_link}"
    host    = "${google_compute_global_address.tor-lb.address}"
    path    = "/*"
  }
}

resource "google_compute_backend_bucket" "tor_deadhole_backend" {
  name        = "${var.name}-deadhole-backend-bucket"
  description = "Unmatched hosts end up in this deadhole"
  bucket_name = "${google_storage_bucket.tor_deadhole.name}"
  enable_cdn  = false

  count = "${local.create_misc}"
}

resource "google_storage_bucket" "tor_deadhole" {
  name     = "${var.name}-deadhole-bucket"
  location = "US"

  count = "${local.create_misc}"
}
