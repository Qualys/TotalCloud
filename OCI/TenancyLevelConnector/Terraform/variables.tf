variable "home_region" {
  description = "Home region of the OCI account"
  type        = string
}

variable "tenancy_id" {
  description = "OCID of the tenancy"
  type        = string
}

variable "audit_user_name" {
  description = "Name of the IAM user for auditing"
  type        = string
  default     = "qualys-audit-user"
}

variable "audit_group_name" {
  description = "Name of the IAM group for auditing"
  type        = string
  default     = "qualys-audit-group"
}
