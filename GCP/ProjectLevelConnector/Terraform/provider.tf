provider terraform {
  required_version = ">=1.0.0"
  required_providers {
    google = {
      version = ">= 4.0"
      project = var.project_id      
    }
  }
}
