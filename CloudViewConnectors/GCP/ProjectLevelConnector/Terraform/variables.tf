variable "project_id" {
  description = "Your GCP project ID"
  type        = string
}

variable "CreateQualysCSPMServiceAccount" {
  description = "Set to true if create Qualys CSPM Service Account, else set to false"
  type        = bool
  default     = true
}
variable "service_account_id" {
  description = "Service account ID"
  type        = string
  default     = "qualyscspmserviceaccount"
}

