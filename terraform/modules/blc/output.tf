output "backend_service" {
  value = "${element(concat(google_compute_backend_service.blc.*.self_link, list("")), 0)}"
}
