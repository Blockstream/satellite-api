output "lb_svc_acct" {
  value = google_service_account.satapi-lb[0].email
}
