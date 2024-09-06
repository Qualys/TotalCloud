# Enable Compute Engine API
resource "google_project_service" "compute_engine" {
  project = var.project_id
  service = "compute.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

# Enable Cloud Resource Manager API
resource "google_project_service" "cloud_resource_manager" {
  project = var.project_id
  service = "cloudresourcemanager.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

# Enable Kubernetes Engine API
resource "google_project_service" "kubernetes_engine" {
  project = var.project_id
  service = "container.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

# Enable Cloud SQL Admin API
resource "google_project_service" "cloud_sql_admin" {
  project = var.project_id
  service = "sqladmin.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

# Enable BigQuery API
resource "google_project_service" "bigquery" {
  project = var.project_id
  service = "bigquery.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

# Enable Cloud Functions API
resource "google_project_service" "cloud_functions" {
  project = var.project_id
  service = "cloudfunctions.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

# Enable Cloud DNS API
resource "google_project_service" "cloud_dns" {
  project = var.project_id
  service = "dns.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

# Enable Cloud Key Management Service (KMS) API
resource "google_project_service" "kms" {
  project = var.project_id
  service = "cloudkms.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

# Enable Cloud Logging API
resource "google_project_service" "cloud_logging" {
  project = var.project_id
  service = "logging.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

# Enable Stackdriver Monitoring API
resource "google_project_service" "stackdriver_monitoring" {
  project = var.project_id
  service = "monitoring.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

# Enable Identity and Access Management (IAM) API
resource "google_project_service" "iam" {
  project = var.project_id
  service = "iam.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

# Enable Cloud Pub/Sub API
resource "google_project_service" "pubsub" {
  project = var.project_id
  service = "pubsub.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

# Enable Service Usage API
resource "google_project_service" "service_usage" {
  project = var.project_id
  service = "serviceusage.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

# Enable Cloud Dataproc API
resource "google_project_service" "dataproc" {
  project = var.project_id
  service = "dataproc.googleapis.com"
  lifecycle {
    prevent_destroy = true
  }
}

data "google_service_account" "QualysCSPMServiceAccountData" {
  project    = var.project_id
  account_id = var.service_account_id
}

# Create a service account
resource "google_service_account" "QualysCSPMServiceAccount" {
  count        = var.CreateQualysCSPMServiceAccount == true ? 1 : 0
  account_id   = var.service_account_id
  display_name = "QualysCSPMServiceAccount"
  project      = var.project_id

  depends_on = [google_project_service.iam]
}

# Assign roles to the service account for the org
resource "google_project_iam_binding" "viewer_member" {
  project = var.project_id
  role    = "roles/viewer"
  members = var.CreateQualysCSPMServiceAccount == true ? ["serviceAccount:${google_service_account.QualysCSPMServiceAccount[0].email}"] : ["serviceAccount:${data.google_service_account.QualysCSPMServiceAccountData.email}"]

  # Specify the dependency on the service account resource
  depends_on = [google_service_account.QualysCSPMServiceAccount]
}

resource "google_project_iam_binding" "security_reviewer_member" {
  project = var.project_id
  role    = "roles/iam.securityReviewer"
  members = var.CreateQualysCSPMServiceAccount == true ? ["serviceAccount:${google_service_account.QualysCSPMServiceAccount[0].email}"] : ["serviceAccount:${data.google_service_account.QualysCSPMServiceAccountData.email}"]

  # Specify the dependency on the service account resource
  depends_on = [google_service_account.QualysCSPMServiceAccount]
}


# Create API Keys
resource "google_service_account_key" "api_keys" {
  service_account_id = var.CreateQualysCSPMServiceAccount == true ? google_service_account.QualysCSPMServiceAccount[0].name : data.google_service_account.QualysCSPMServiceAccountData.name

  # Specify the dependency on the service account resource
  depends_on = [google_service_account.QualysCSPMServiceAccount]
}

resource "local_file" "key" {
  filename = "${path.module}/key.json"
  content  = base64decode(google_service_account_key.api_keys.private_key)
}
