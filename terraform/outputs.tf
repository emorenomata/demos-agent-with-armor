output "load_balancer_ip" {
  description = "Public IP Address of the Load Balancer protected by Cloud Armor"
  value       = module.load_balancer.external_ip
}

output "application_url" {
  description = "Entrypoint URL for the Armor Agent Chat UI"
  value       = module.load_balancer.load_balancer_url
}

output "cloud_run_service_name" {
  description = "Cloud Run Service Name"
  value       = module.cloud_run.service_name
}

output "cloud_armor_policy_name" {
  description = "Cloud Armor Security Policy Name"
  value       = module.cloud_armor.security_policy_name
}

output "model_armor_template_id" {
  description = "Configured Model Armor Template ID"
  value       = module.model_armor.template_id
}
