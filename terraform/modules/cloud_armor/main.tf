resource "google_compute_security_policy" "cloud_armor_policy" {
  name        = var.policy_name
  project     = var.project_id
  description = "Cloud Armor WAF, Geo-blocking and Rate Limiting for Armor Agent"

  # Rule 900: OWASP Preconfigured WAF Rules (SQLi & XSS protection at Edge - sensitivity 1 to avoid JSON false positives)
  rule {
    action   = "deny(403)"
    priority = "900"
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 1}) || evaluatePreconfiguredWaf('xss-v33-stable', {'sensitivity': 1})"
      }
    }
    description = "Block OWASP SQLi and XSS attacks at the perimeter"
  }

  # Rule 1000: Geo-blocking / Allowed Country Codes (if specified, block non-matching countries)
  dynamic "rule" {
    for_each = length(var.allowed_regions) > 0 ? [1] : []
    content {
      action   = "deny(403)"
      priority = "1000"
      match {
        expr {
          expression = "!(${join(" || ", [for r in var.allowed_regions : "origin.region_code == '${r}'"])})"
        }
      }
      description = "Deny requests outside permitted countries"
    }
  }

  # Rule 2000: Rate Limiting (DDoS / Scraping protection)
  rule {
    action   = "rate_based_ban"
    priority = "2000"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = var.allowed_ips
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"
      rate_limit_threshold {
        count        = var.rate_limit_count
        interval_sec = var.rate_limit_interval_sec
      }
      ban_threshold {
        count        = var.rate_limit_count * 2
        interval_sec = var.rate_limit_interval_sec
      }
      ban_duration_sec = 300
    }
    description = "Rate limiting protection against DDoS and scraping for allowed IPs"
  }

  # Default Fallback Rule (deny if specific IP allowlist is used, otherwise allow)
  rule {
    action   = contains(var.allowed_ips, "0.0.0.0/0") || contains(var.allowed_ips, "*") ? "allow" : "deny(403)"
    priority = "2147483647"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Default fallback rule"
  }
}
