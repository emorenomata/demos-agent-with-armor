resource "google_compute_security_policy" "cloud_armor_policy" {
  name        = var.policy_name
  project     = var.project_id
  description = "Cloud Armor WAF, Geo-blocking and Rate Limiting for Armor Agent"

  # Rule 1000: Rate Limiting
  rule {
    action   = "rate_based_ban"
    priority = "1000"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
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
    description = "Rate limiting protection against DDoS and scraping"
  }

  # Rule 2000: Geo-blocking / Allowed Country Codes (if specified)
  dynamic "rule" {
    for_each = length(var.allowed_regions) > 0 ? [1] : []
    content {
      action   = "allow"
      priority = "2000"
      match {
        expr {
          expression = join(" || ", [for r in var.allowed_regions : "origin.region_code == '${r}'"])
        }
      }
      description = "Allow requests only from permitted countries"
    }
  }

  # Rule 3000: IP Allowlist
  rule {
    action   = "allow"
    priority = "3000"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = var.allowed_ips
      }
    }
    description = "Allow configured IP ranges"
  }

  # Rule 4000: OWASP Preconfigured WAF Rules (SQLi & XSS protection at Edge)
  rule {
    action   = "deny(403)"
    priority = "4000"
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('sqli-v33-stable') || evaluatePreconfiguredExpr('xss-v33-stable')"
      }
    }
    description = "Block OWASP SQLi and XSS attacks at the perimeter"
  }

  # Default Fallback Rule (deny or allow based on whether IP/Geo restrictions are enforced)
  rule {
    action   = length(var.allowed_regions) > 0 ? "deny(403)" : "allow"
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
