output "lb_svc_acct" {
  value = length(google_service_account.satapi-lb) > 0 ? google_service_account.satapi-lb[0].email : ""
}

output "backend_service" {
  value = length(google_compute_backend_service.satapi-lb) > 0 ? google_compute_backend_service.satapi-lb[0].self_link : ""
}

output "backend_service_tor" {
  value = length(google_compute_backend_service.satapi-lb-tor) > 0 ? google_compute_backend_service.satapi-lb-tor[0].self_link : ""
}

output "internal_ip" {
  value = length(google_compute_address.satapi-lb-internal) > 0 ? google_compute_address.satapi-lb-internal[0].address : ""
}
