variable "project_id" {
  type = string
}

variable "location" {
  type    = string
  default = "us-central1"
}

variable "template_id" {
  type    = string
  default = "armor-agent-template"
}
