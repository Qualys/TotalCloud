variable "application_display_name" {
  description = "The display name of the Azure AD application"
  type        = string
  default     = "example-app"
}

variable "secret_key_expiry" {
  description = "The expiry duration for the application secret key"
  type        = string
  default     = "240h"
}

variable "secret_key_filename" {
  description = "The filename for storing the secret key"
  type        = string
  default     = "secret_key.txt"
}
