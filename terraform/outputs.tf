# Production only (tor)
output "blc_backend_service_testnet" {
  value = "${module.blc-testnet.backend_service}"
}

output "blc_backend_service_mainnet" {
  value = "${module.blc-mainnet.backend_service}"
}

output "prom_svc_acct" {
  value = "${module.prometheus.prom_svc_acct}"
}
