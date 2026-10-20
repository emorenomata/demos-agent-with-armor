data "google_project" "current" {
  project_id = var.project_id
}

# Enable Model Armor & DLP APIs
resource "google_project_service" "model_armor_api" {
  project            = var.project_id
  service            = "modelarmor.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "dlp_api" {
  project            = var.project_id
  service            = "dlp.googleapis.com"
  disable_on_destroy = false
}

# Automated Provisioning of Vertex AI Service Agent IAM + Model Armor Floor Settings & Template
resource "terraform_data" "model_armor_template" {
  input = {
    project_id     = var.project_id
    project_number = data.google_project.current.number
    location       = var.location
    template_id    = var.template_id
  }

  provisioner "local-exec" {
    command = <<-EOT
      # 1. Ensure Vertex AI Service Identity exists and has Model Armor + DLP permissions for Floor Settings
      gcloud beta services identity create --service=aiplatform.googleapis.com --project=${var.project_id} 2>/dev/null || true
      gcloud projects add-iam-policy-binding ${var.project_id} \
        --member="serviceAccount:service-${data.google_project.current.number}@gcp-sa-aiplatform.iam.gserviceaccount.com" \
        --role="roles/modelarmor.user" --quiet >/dev/null 2>&1 || true
      gcloud projects add-iam-policy-binding ${var.project_id} \
        --member="serviceAccount:service-${data.google_project.current.number}@gcp-sa-aiplatform.iam.gserviceaccount.com" \
        --role="roles/dlp.user" --quiet >/dev/null 2>&1 || true

      # 2. Configure Project-level Model Armor Floor Settings (AI_PLATFORM + INSPECT_AND_BLOCK)
      ACCESS_TOKEN=$(gcloud auth application-default print-access-token 2>/dev/null || gcloud auth print-access-token 2>/dev/null || echo "")
      if [ -n "$ACCESS_TOKEN" ]; then
        curl -s -X PATCH \
          -H "Authorization: Bearer $ACCESS_TOKEN" \
          -H "Content-Type: application/json" \
          "https://modelarmor.googleapis.com/v1/projects/${var.project_id}/locations/global/floorSetting?updateMask=filterConfig,enableFloorSettingEnforcement,integratedServices,aiPlatformFloorSetting" \
          -d '{
            "enableFloorSettingEnforcement": true,
            "integratedServices": ["AI_PLATFORM"],
            "aiPlatformFloorSetting": {
              "inspectAndBlock": true,
              "enableCloudLogging": true
            },
            "filterConfig": {
              "raiSettings": {
                "raiFilters": [
                  {"filterType": "HATE_SPEECH", "confidenceLevel": "MEDIUM_AND_ABOVE"},
                  {"filterType": "HARASSMENT", "confidenceLevel": "MEDIUM_AND_ABOVE"},
                  {"filterType": "DANGEROUS", "confidenceLevel": "MEDIUM_AND_ABOVE"},
                  {"filterType": "SEXUALLY_EXPLICIT", "confidenceLevel": "MEDIUM_AND_ABOVE"}
                ]
              },
              "piAndJailbreakFilterSettings": {
                "filterEnforcement": "ENABLED",
                "confidenceLevel": "LOW_AND_ABOVE"
              },
              "maliciousUriFilterSettings": {
                "filterEnforcement": "ENABLED"
              },
              "sdpSettings": {
                "basicConfig": {
                  "filterEnforcement": "ENABLED"
                }
              }
            }
          }' || true

        # 3. Create or update regional diagnostic Model Armor Template
        curl -s -X POST \
          -H "Authorization: Bearer $ACCESS_TOKEN" \
          -H "Content-Type: application/json" \
          "https://modelarmor.${var.location}.rep.googleapis.com/v1/projects/${var.project_id}/locations/${var.location}/templates?templateId=${var.template_id}" \
          -d '{
            "filterConfig": {
              "raiSettings": {
                "raiFilters": [
                  {"filterType": "HATE_SPEECH", "confidenceLevel": "MEDIUM_AND_ABOVE"},
                  {"filterType": "HARASSMENT", "confidenceLevel": "MEDIUM_AND_ABOVE"},
                  {"filterType": "DANGEROUS", "confidenceLevel": "MEDIUM_AND_ABOVE"},
                  {"filterType": "SEXUALLY_EXPLICIT", "confidenceLevel": "MEDIUM_AND_ABOVE"}
                ]
              },
              "piAndJailbreakFilterSettings": {
                "filterEnforcement": "ENABLED",
                "confidenceLevel": "LOW_AND_ABOVE"
              },
              "maliciousUriFilterSettings": {
                "filterEnforcement": "ENABLED"
              },
              "sdpSettings": {
                "basicConfig": {
                  "filterEnforcement": "ENABLED"
                }
              }
            }
          }' || true
      fi
    EOT
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      ACCESS_TOKEN=$(gcloud auth application-default print-access-token 2>/dev/null || gcloud auth print-access-token 2>/dev/null || echo "")
      if [ -n "$ACCESS_TOKEN" ]; then
        curl -s -X DELETE \
          -H "Authorization: Bearer $ACCESS_TOKEN" \
          "https://modelarmor.${self.input.location}.rep.googleapis.com/v1/projects/${self.input.project_id}/locations/${self.input.location}/templates/${self.input.template_id}" || true
      fi
    EOT
  }

  depends_on = [google_project_service.model_armor_api, google_project_service.dlp_api]
}

# Output placeholder for template identifier reference
locals {
  full_template_name = "projects/${var.project_id}/locations/${var.location}/templates/${var.template_id}"
}
