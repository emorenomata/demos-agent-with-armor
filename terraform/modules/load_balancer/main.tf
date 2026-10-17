# 1. Serverless Network Endpoint Group (NEG) for Cloud Run
resource "google_compute_region_network_endpoint_group" "serverless_neg" {
  name                  = "${var.lb_name}-neg"
  project               = var.project_id
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = var.cloud_run_service_name
  }
}

# 2. Backend Service with Cloud Armor Security Policy Attached
resource "google_compute_backend_service" "backend_service" {
  name                  = "${var.lb_name}-backend"
  project               = var.project_id
  security_policy       = var.security_policy_id
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.serverless_neg.id
  }
}

# 3. URL Map
resource "google_compute_url_map" "url_map" {
  name            = "${var.lb_name}-url-map"
  project         = var.project_id
  default_service = google_compute_backend_service.backend_service.id
}

# 4. Target HTTP Proxy
resource "google_compute_target_http_proxy" "http_proxy" {
  name    = "${var.lb_name}-http-proxy"
  project = var.project_id
  url_map = google_compute_url_map.url_map.id
}

# 5. Global Reserved IP
resource "google_compute_global_address" "lb_ip" {
  name    = "${var.lb_name}-ip"
  project = var.project_id
}

# 6. Global Forwarding Rule
resource "google_compute_global_forwarding_rule" "forwarding_rule" {
  name                  = "${var.lb_name}-forwarding-rule"
  project               = var.project_id
  ip_protocol           = "TCP"
  port_range            = "80"
  target                = google_compute_target_http_proxy.http_proxy.id
  ip_address            = google_compute_global_address.lb_ip.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
