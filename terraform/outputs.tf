# Internal IP used for proxy_pass-ing to correct instance (mainnet vs testnet)
output "blc_internal_ip_testnet" {
  value = module.blc-testnet.internal_ip
}

# Remote service accounts used for firewall rules
output "prom_svc_acct" {
  value = module.prometheus.prom_svc_acct
}

output "lb_svc_acct" {
  value = module.lb.lb_svc_acct
}

output "lb_backend_service" {
  value = module.lb.backend_service
}