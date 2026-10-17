variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "Default GCP Region"
  type        = string
  default     = "us-central1"
}

variable "app_name" {
  description = "Application and resource naming prefix"
  type        = string
  default     = "armor-agent"
}

variable "container_image" {
  description = "Container image URL to deploy to Cloud Run"
  type        = string
  default     = "gcr.io/cloudrun/hello" # Placeholder until built, can be overridden
}

variable "gemini_api_key" {
  description = "Optional Gemini API Key (if not using Vertex AI ADC)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "allowed_ips" {
  description = "List of CIDR blocks permitted by Cloud Armor. If empty, allows all."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "allowed_regions" {
  description = "List of ISO country codes allowed by Cloud Armor (e.g. ['MX', 'US']). Leave empty to allow all."
  type        = list(string)
  default     = []
}

variable "rate_limit_count" {
  description = "Maximum requests allowed per client IP within the rate limit window"
  type        = number
  default     = 120
}

variable "rate_limit_interval_sec" {
  description = "Interval in seconds for rate limiting"
  type        = number
  default     = 60
}

variable "model_armor_template_id" {
  description = "Identifier for the Model Armor Template"
  type        = string
  default     = "armor-agent-template"
}
