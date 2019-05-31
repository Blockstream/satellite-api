output "prom_svc_acct" {
  value = element(concat(google_service_account.prometheus.*.email, [""]), 0)
}

