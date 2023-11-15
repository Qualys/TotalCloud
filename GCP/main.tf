#Read project IDs from a text file
variable "project_ids_file" {
  default = "project_ids.txt"
}

locals {
  project_ids = split("\n", file(var.project_ids_file))
}


# Enable Compute Engine API
resource "google_project_service" "compute_engine" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "compute.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}

# Enable Cloud Resource Manager API
resource "google_project_service" "cloud_resource_manager" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "cloudresourcemanager.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}

# Enable Kubernetes Engine API
resource "google_project_service" "kubernetes_engine" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "container.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}

# Enable Cloud SQL Admin API
resource "google_project_service" "cloud_sql_admin" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "sqladmin.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}

# Enable BigQuery API
resource "google_project_service" "bigquery" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "bigquery.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}

# Enable Cloud Functions API
resource "google_project_service" "cloud_functions" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "cloudfunctions.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}

# Enable Cloud DNS API
resource "google_project_service" "cloud_dns" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "dns.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}

# Enable Cloud Key Management Service (KMS) API
resource "google_project_service" "kms" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "cloudkms.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}

# Enable Cloud Logging API
resource "google_project_service" "cloud_logging" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "logging.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}

# Enable Stackdriver Monitoring API
resource "google_project_service" "stackdriver_monitoring" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "monitoring.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}

# Enable Identity and Access Management (IAM) API
resource "google_project_service" "iam" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "iam.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}

# Enable Cloud Pub/Sub API
resource "google_project_service" "pubsub" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "pubsub.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}

# Enable Service Usage API
resource "google_project_service" "service_usage" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "serviceusage.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}

# Enable Cloud Dataproc API
resource "google_project_service" "dataproc" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "dataproc.googleapis.com"
  lifecycle {
        prevent_destroy = true
    }
}
