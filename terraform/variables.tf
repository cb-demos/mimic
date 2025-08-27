variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for deployment"
  type        = string
  default     = "us-central1"
}

variable "domain" {
  description = "Domain name"
  type        = string
}

variable "dns_zone_name" {
  description = "Cloud DNS zone name for your domain"
  type        = string
}

variable "zone" {
  description = "GCP zone for the instance"
  type        = string
  default     = "us-central1-c"
}

variable "admin_email" {
  description = "Email address for SSL certificate registration"
  type        = string
}

