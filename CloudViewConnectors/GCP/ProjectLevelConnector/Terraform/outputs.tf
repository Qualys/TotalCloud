output "api_keys_json" {
  value     = google_service_account_key.api_keys.private_key
  sensitive = true
}

output "service_account_email" {
  value = var.CreateQualysCSPMServiceAccount == true ? google_service_account.QualysCSPMServiceAccount[0].email : data.google_service_account.QualysCSPMServiceAccountData.email
}

output "project_id" {
  value = var.project_id
}
