terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Enable Required GCP APIs
resource "google_project_service" "enabled_apis" {
  for_each = toset([
    "run.googleapis.com",
    "compute.googleapis.com",
    "aiplatform.googleapis.com",
    "modelarmor.googleapis.com",
    "dlp.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com"
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# 2. Cloud Armor Security Policy Module
module "cloud_armor" {
  source = "./modules/cloud_armor"

  project_id              = var.project_id
  policy_name             = "${var.app_name}-armor-policy"
  allowed_ips             = var.allowed_ips
  allowed_regions         = var.allowed_regions
  rate_limit_count        = var.rate_limit_count
  rate_limit_interval_sec = var.rate_limit_interval_sec

  depends_on = [google_project_service.enabled_apis]
}

# 3. Model Armor Module
module "model_armor" {
  source = "./modules/model_armor"

  project_id  = var.project_id
  location    = var.region
  template_id = var.model_armor_template_id

  depends_on = [google_project_service.enabled_apis]
}

# 4. Cloud Run Service Module
module "cloud_run" {
  source = "./modules/cloud_run"

  project_id              = var.project_id
  region                  = var.region
  service_name            = "${var.app_name}-service"
  container_image         = var.container_image
  gemini_api_key          = var.gemini_api_key
  model_armor_template_id = module.model_armor.template_id

  depends_on = [google_project_service.enabled_apis]
}

# 5. External HTTPS Load Balancer with Cloud Armor Protection
module "load_balancer" {
  source = "./modules/load_balancer"

  project_id             = var.project_id
  region                 = var.region
  lb_name                = "${var.app_name}-lb"
  cloud_run_service_name = module.cloud_run.service_name
  security_policy_id     = module.cloud_armor.security_policy_id

  depends_on = [module.cloud_run, module.cloud_armor]
}
