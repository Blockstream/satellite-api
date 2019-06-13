output "backend_service" {
  value = google_compute_backend_service.blc[0].self_link
}

output "internal_ip" {
  value = google_compute_address.blc-internal[0].address
}
