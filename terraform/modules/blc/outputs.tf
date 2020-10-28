output "internal_ip" {
  #value = google_compute_address.blc-internal[0].address
  value = length(google_compute_address.blc-internal) > 0 ? google_compute_address.blc-internal[0].address : ""
}
