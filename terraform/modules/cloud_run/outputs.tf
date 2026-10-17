output "service_name" {
  description = "Name of the Cloud Run service"
  value       = google_cloud_run_v2_service.app_service.name
}

output "service_uri" {
  description = "URI of the Cloud Run service"
  value       = google_cloud_run_v2_service.app_service.uri
}

output "service_account_email" {
  description = "Service account email running Cloud Run"
  value       = google_service_account.cloud_run_sa.email
}
