resource "tls_private_key" "audit_user_key" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "local_file" "private_key" {
  content  = tls_private_key.audit_user_key.private_key_pem
  filename = "${path.module}/oci_api_key.pem"
}

resource "oci_identity_user" "audit_user" {
  name           = var.audit_user_name
  description    = "User for Qualys access"
  compartment_id = var.tenancy_id
}

resource "oci_identity_group" "audit_group" {
  name           = var.audit_group_name
  description    = "Group for Qualys access"
  compartment_id = var.tenancy_id
}

resource "oci_identity_user_group_membership" "audit_user_membership" {
  user_id  = oci_identity_user.audit_user.id
  group_id = oci_identity_group.audit_group.id
}

resource "oci_identity_policy" "audit_policy" {
  name           = "${var.audit_group_name}-policy"
  description    = "Policy to allow the audit group to perform necessary actions"
  compartment_id = var.tenancy_id

  statements = [
    "Allow group ${oci_identity_group.audit_group.name} to manage all-resources in tenancy"
  ]
}

resource "oci_identity_api_key" "audit_user_api_key" {
  user_id   = oci_identity_user.audit_user.id
  key_value = tls_private_key.audit_user_key.public_key_pem
}
