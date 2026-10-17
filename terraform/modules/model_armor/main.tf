# Enable Model Armor API
resource "google_project_service" "model_armor_api" {
  project            = var.project_id
  service            = "modelarmor.googleapis.com"
  disable_on_destroy = false
}

# Automated Provisioning of Model Armor Template via GCP API
resource "terraform_data" "model_armor_template" {
  input = {
    project_id  = var.project_id
    location    = var.location
    template_id = var.template_id
  }

  provisioner "local-exec" {
    command = <<-EOT
      ACCESS_TOKEN=$(gcloud auth print-access-token 2>/dev/null || echo "")
      if [ -n "$ACCESS_TOKEN" ]; then
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
                "confidenceLevel": "MEDIUM_AND_ABOVE"
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
      ACCESS_TOKEN=$(gcloud auth print-access-token 2>/dev/null || echo "")
      if [ -n "$ACCESS_TOKEN" ]; then
        curl -s -X DELETE \
          -H "Authorization: Bearer $ACCESS_TOKEN" \
          "https://modelarmor.${self.input.location}.rep.googleapis.com/v1/projects/${self.input.project_id}/locations/${self.input.location}/templates/${self.input.template_id}" || true
      fi
    EOT
  }

  depends_on = [google_project_service.model_armor_api]
}

# Output placeholder for template identifier reference
locals {
  full_template_name = "projects/${var.project_id}/locations/${var.location}/templates/${var.template_id}"
}
