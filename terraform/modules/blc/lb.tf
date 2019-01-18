# Forwarding rules
resource "google_compute_global_forwarding_rule" "rule-https" {
  name        = "${var.name}-https-forwarding-rule-${var.env}"
  target      = "${google_compute_target_https_proxy.https-proxy.self_link}"
  port_range  = "443"
  ip_protocol = "TCP"
  ip_address  = "${google_compute_global_address.lb.address}"
  count       = "${var.create_resources}"
}

resource "google_compute_global_forwarding_rule" "rule-http" {
  name        = "${var.name}-http-forwarding-rule-${var.env}"
  target      = "${google_compute_target_http_proxy.http-proxy.self_link}"
  port_range  = "80"
  ip_protocol = "TCP"
  ip_address  = "${google_compute_global_address.lb.address}"
  count       = "${var.create_resources}"
}

# Target proxies
resource "google_compute_target_http_proxy" "http-proxy" {
  name    = "${var.name}-http-proxy-${var.env}"
  url_map = "${google_compute_url_map.http.self_link}"
  count   = "${var.create_resources}"
}

resource "google_compute_target_https_proxy" "https-proxy" {
  name             = "${var.name}-https-proxy-${var.env}"
  url_map          = "${google_compute_url_map.https.self_link}"
  ssl_certificates = ["${var.ssl_cert}"]
  count            = "${var.create_resources}"
}

# URL maps
resource "google_compute_url_map" "http" {
  name            = "${var.name}-http-urlmap-${var.env}"
  default_service = "${google_compute_backend_service.blc.self_link}"
  count           = "${var.create_resources}"

  host_rule {
    hosts        = ["${var.host}"]
    path_matcher = "allpaths"
  }

  path_matcher {
    name            = "allpaths"
    default_service = "${google_compute_backend_service.blc.self_link}"

    path_rule {
      paths   = ["/*"]
      service = "${google_compute_backend_service.blc.self_link}"
    }
  }
}

resource "google_compute_url_map" "https" {
  name            = "${var.name}-https-urlmap-${var.env}"
  default_service = "${google_compute_backend_service.blc.self_link}"
  count           = "${var.create_resources}"

  host_rule {
    hosts        = ["${var.host}"]
    path_matcher = "allpaths"
  }

  path_matcher {
    name            = "allpaths"
    default_service = "${google_compute_backend_service.blc.self_link}"

    path_rule {
      paths   = ["/*"]
      service = "${google_compute_backend_service.blc.self_link}"
    }
  }
}
