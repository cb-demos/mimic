terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "mimic-tf-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Data sources for existing secrets
data "google_secret_manager_secret" "github_token" {
  secret_id = "mimic-github-token"
}

data "google_secret_manager_secret" "cloudbees_endpoint_id" {
  secret_id = "mimic-cloudbees-endpoint-id"
}

# Service account for GCE instance (pre-existing)
data "google_service_account" "mimic_service" {
  account_id = "mimic-service"
}

# Firewall rule - Deny all ingress (priority 1000)
resource "google_compute_firewall" "deny_all" {
  name     = "mimic-deny-all"
  network  = "default"
  priority = 1000

  deny {
    protocol = "all"
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["mimic-deny"]

  description = "Deny all traffic to mimic instances"
}

# Firewall rule - Allow Tailscale IPs (priority 100)
resource "google_compute_firewall" "allow_tailscale" {
  name     = "mimic-allow-tailscale"
  network  = "default"
  priority = 100

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "22"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [
    "10.131.85.211/32",
    "34.224.186.68/32",
    "13.202.29.142/32",
    "3.24.64.154/32",
    "18.192.84.235/32"
  ]

  target_tags = ["mimic-allow"]

  description = "Allow Tailscale VPN access to mimic instances"
}


# Static IP address
resource "google_compute_address" "mimic" {
  name   = "mimic-static-ip"
  region = var.region
}

# GCE Instance
resource "google_compute_instance" "mimic" {
  name         = "mimic-server"
  machine_type = "e2-small"
  zone         = var.zone
  allow_stopping_for_update = true

  tags = ["mimic-allow", "mimic-deny"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 10
    }
  }

  network_interface {
    network    = "default"
    subnetwork = "projects/${var.project_id}/regions/${var.region}/subnetworks/default"

    access_config {
      nat_ip = google_compute_address.mimic.address
    }
  }

  service_account {
    email  = data.google_service_account.mimic_service.email
    scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }

  metadata_startup_script = templatefile("${path.module}/startup-script.sh", {
    project_id  = var.project_id
    domain      = var.domain
    admin_email = var.admin_email
  })
}

# DNS A record
resource "google_dns_record_set" "mimic_a_record" {
  name         = "${var.domain}."
  managed_zone = var.dns_zone_name
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_address.mimic.address]
}

# Outputs
output "instance_ip" {
  description = "Static IP address of the mimic instance"
  value       = google_compute_address.mimic.address
}

output "instance_name" {
  description = "Name of the mimic instance"
  value       = google_compute_instance.mimic.name
}

output "service_url" {
  description = "Service URL"
  value       = "https://${var.domain}"
}
