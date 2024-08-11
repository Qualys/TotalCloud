# Generate the key pair
resource "tls_private_key" "audit_user_key" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

# Save the private key to a file (ensure this is secure and not checked into version control)
resource "local_file" "private_key" {
  content  = tls_private_key.audit_user_key.private_key_pem
  filename = "${path.module}/oci_api_key.pem"
}

# Create IAM User
resource "oci_identity_user" "audit_user" {
  name           = var.audit_user_name
  description    = "User for Qualys access"
  compartment_id = var.tenancy_id
}

# Create IAM Group
resource "oci_identity_group" "audit_group" {
  name           = var.audit_group_name
  description    = "Group for Qualys access"
  compartment_id = var.tenancy_id
}

# Add User to Group
resource "oci_identity_group_membership" "audit_user_membership" {
  user_id  = oci_identity_user.audit_user.id
  group_id = oci_identity_group.audit_group.id
}

# Create a policy to define the required permissions for the audit group
resource "oci_identity_policy" "audit_policy" {
  name           = "${var.audit_group_name}-policy"
  description    = "Policy to allow the audit group to perform necessary actions"
  compartment_id = var.tenancy_id

  # Customize the policy statements based on your requirements.
  statements = [
    "Allow group ${oci_identity_group.audit_group.name} to manage all-resources in compartment ${var.tenancy_id}"
  ]
}

# Generate and upload API Key for the IAM User
resource "oci_identity_api_key" "audit_user_api_key" {
  user_id   = oci_identity_user.audit_user.id
  key_value = tls_private_key.audit_user_key.public_key_pem
}
