variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "lb_name" {
  type    = string
  default = "armor-agent-lb"
}

variable "cloud_run_service_name" {
  type = string
}

variable "security_policy_id" {
  type        = string
  description = "Cloud Armor Security Policy ID"
}
