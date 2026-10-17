variable "project_id" {
  type = string
}

variable "policy_name" {
  type    = string
  default = "armor-agent-waf-policy"
}

variable "allowed_ips" {
  type    = list(string)
  default = ["0.0.0.0/0"]
}

variable "allowed_regions" {
  type    = list(string)
  default = []
}

variable "rate_limit_count" {
  type    = number
  default = 120
}

variable "rate_limit_interval_sec" {
  type    = number
  default = 60
}
