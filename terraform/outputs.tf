output "blc_backend_service" {
  value = "${module.blc.backend_service}"
}

output "prom_sa" {
  value = "${module.prometheus.prom_svc_acct}"
}
