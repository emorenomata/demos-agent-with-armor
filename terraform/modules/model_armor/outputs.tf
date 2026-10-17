output "template_id" {
  description = "The Model Armor template ID"
  value       = var.template_id
}

output "template_resource_name" {
  description = "Full resource name of the template"
  value       = local.full_template_name
}
