output "tenant_ocid" {
  description = "OCID of the tenancy"
  value       = var.tenancy_id
}

output "user_ocid" {
  description = "OCID of the created IAM user"
  value       = oci_identity_user.audit_user.id
}

output "region" {
  description = "Region where the resources are created"
  value       = var.home_region
}

output "private_key_path" {
  description = "Path to the generated private key"
  value       = local_file.private_key.filename
}

output "api_key_fingerprint" {
  description = "Fingerprint of the generated API key"
  value       = oci_identity_api_key.audit_user_api_key.fingerprint
}
