output "internal_ip" {
  value = google_compute_address.blc-internal[0].address
}
