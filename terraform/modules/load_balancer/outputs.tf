output "external_ip" {
  description = "The external IPv4 address of the Load Balancer"
  value       = google_compute_global_address.lb_ip.address
}

output "load_balancer_url" {
  description = "The full HTTP entry URL protected by Cloud Armor"
  value       = "http://${google_compute_global_address.lb_ip.address}"
}
