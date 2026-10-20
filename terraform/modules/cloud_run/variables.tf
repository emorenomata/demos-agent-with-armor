variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "service_name" {
  type    = string
  default = "armor-agent-service"
}

variable "container_image" {
  type = string
}

variable "gemini_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "model_armor_template_id" {
  type    = string
  default = "armor-agent-template"
}

variable "agent_engine_resource_name" {
  type    = string
  default = ""
}

