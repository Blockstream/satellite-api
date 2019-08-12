output "lb_svc_acct" {
  value = google_service_account.satapi-lb[0].email
}

output "backend_service" {
  value = google_compute_backend_service.satapi-lb[0].self_link
}

output "lb_cert_bucket" {
  value = google_storage_bucket.satapi-lb-private[0].self_link
}
