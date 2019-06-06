# IP address
resource "google_compute_global_address" "lb" {
  name    = "satellite-api-client-lb-${local.env}"
  project = var.project
  count   = local.create_mainnet
}

# Forwarding rules
resource "google_compute_global_forwarding_rule" "rule-https" {
  name        = "satellite-api-https-forwarding-rule-${local.env}"
  target      = google_compute_target_https_proxy.https-proxy[0].self_link
  port_range  = "443"
  ip_protocol = "TCP"
  ip_address  = google_compute_global_address.lb[0].address
  project     = var.project
  count       = local.create_mainnet
}

resource "google_compute_global_forwarding_rule" "rule-http" {
  name        = "satellite-api-http-forwarding-rule-${local.env}"
  target      = google_compute_target_http_proxy.http-proxy[0].self_link
  port_range  = "80"
  ip_protocol = "TCP"
  ip_address  = google_compute_global_address.lb[0].address
  project     = var.project
  count       = local.create_mainnet
}

# Target proxies
resource "google_compute_target_http_proxy" "http-proxy" {
  name    = "satellite-api-http-proxy-${local.env}"
  url_map = google_compute_url_map.http[0].self_link
  project = var.project
  count   = local.create_mainnet
}

resource "google_compute_target_https_proxy" "https-proxy" {
  name             = "satellite-api-https-proxy-${local.env}"
  url_map          = google_compute_url_map.https[0].self_link
  ssl_certificates = [var.ssl_cert]
  project          = var.project
  count            = local.create_mainnet
}

# URL maps
resource "google_compute_url_map" "http" {
  name            = "satellite-api-http-urlmap-${local.env}"
  default_service = data.terraform_remote_state.blc-mainnet.outputs.blc_backend_service_mainnet
  project         = var.project
  count           = local.create_mainnet

  host_rule {
    hosts        = [var.host]
    path_matcher = "allpaths"
  }

  path_matcher {
    name            = "allpaths"
    default_service = data.terraform_remote_state.blc-mainnet.outputs.blc_backend_service_mainnet

    path_rule {
      paths   = ["/*"]
      service = data.terraform_remote_state.blc-mainnet.outputs.blc_backend_service_mainnet
    }

    path_rule {
      paths   = ["/testnet", "/testnet/*", "/api", "/api/*"]
      service = data.terraform_remote_state.blc-testnet.outputs.blc_backend_service_testnet
    }
  }
}

resource "google_compute_url_map" "https" {
  name            = "satellite-api-https-urlmap-${local.env}"
  default_service = data.terraform_remote_state.blc-mainnet.outputs.blc_backend_service_mainnet
  project         = var.project
  count           = local.create_mainnet

  host_rule {
    hosts        = [var.host]
    path_matcher = "allpaths"
  }

  path_matcher {
    name            = "allpaths"
    default_service = data.terraform_remote_state.blc-mainnet.outputs.blc_backend_service_mainnet

    path_rule {
      paths   = ["/*"]
      service = data.terraform_remote_state.blc-mainnet.outputs.blc_backend_service_mainnet
    }

    path_rule {
      paths   = ["/testnet", "/testnet/*", "/api", "/api/*"]
      service = data.terraform_remote_state.blc-testnet.outputs.blc_backend_service_testnet
    }
  }
}

