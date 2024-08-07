variable "project_id" {
  description = "Your GCP project ID"
  type        = string
}

variable "service_account_id" {
  description = "Service account ID"
  type        = string
  default     = "qualyscspmserviceaccount"
}
