# Service Account for Cloud Run
resource "google_service_account" "cloud_run_sa" {
  account_id   = "${var.service_name}-sa"
  display_name = "Service Account for Armor Agent Cloud Run"
  project      = var.project_id
}

# IAM Permissions for Vertex AI, Model Armor and Logging
resource "google_project_iam_member" "vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "model_armor_user" {
  project = var.project_id
  role    = "roles/modelarmor.user"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "model_armor_admin" {
  project = var.project_id
  role    = "roles/modelarmor.admin"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "dlp_user" {
  project = var.project_id
  role    = "roles/dlp.user"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "log_viewer" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Cloud Run v2 Service
resource "google_cloud_run_v2_service" "app_service" {
  name     = var.service_name
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL" # Accessible via Cloud Armor Load Balancer AND direct HTTPS Cloud Run URL for demos

  template {
    service_account = google_service_account.cloud_run_sa.email
    timeout         = "120s"

    scaling {
      min_instance_count = 1
      max_instance_count = 20
    }

    containers {
      image = var.container_image

      resources {
        cpu_idle          = false
        startup_cpu_boost = true
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_LOCATION"
        value = var.region
      }
      env {
        name  = "MODEL_ARMOR_TEMPLATE_ID"
        value = var.model_armor_template_id
      }
      env {
        name  = "MODEL_ARMOR_LOCATION"
        value = var.region
      }
      env {
        name  = "AGENT_ENGINE_RESOURCE_NAME"
        value = var.agent_engine_resource_name
      }
      env {
        name  = "GEMINI_API_KEY"
        value = var.gemini_api_key
      }
    }
  }
}

# Allow Load Balancer (Serverless NEG) to invoke Cloud Run
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
