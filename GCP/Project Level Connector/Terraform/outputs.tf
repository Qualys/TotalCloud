output "api_keys_json" {
  value     = google_service_account_key.api_keys.private_key
  sensitive = true
}

output "service_account_email" {
  value = google_service_account.QualysCSPMServiceAccount.email
}

output "project_id" {
  value = var.project_id
}
