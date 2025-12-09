###############################
#  DEPLOYMENT TOGGLES         #
###############################

variable "deploy_totalcloud_cspm_role" {
  type        = bool
  default     = true
  description = "Deploy Qualys CSPM (Cloud Security Posture Management)"
}

variable "deploy_zero_touch_api_based_assessment" {
  type        = bool
  default     = true
  description = "Deploy Qualys Zero-Touch (agentless) connector"
}

variable "deploy_guardduty_integration" {
  type        = bool
  default     = true
  description = "Enable GuardDuty integration"
}

variable "deploy_service_account_for_snapshot_assessment" {
  type        = bool
  default     = true
  description = "Deploy Qualys Snapshot Scanner for EC2 & EBS"
}

variable "deploy_eventbridge_integration" {
  type        = bool
  default     = true
  description = "Deploy Qualys EventBridge Integration"
}

variable "deploy_target_account_for_snapshot_assessment" {
  type        = bool
  default     = true
  description = "Deploy Snapshot Scanner Target account"
}

###############################
#  QUALYS ACCOUNT & AUTH      #
###############################

variable "qualys_cspm_account" {
  type        = string
  description = "12-digit AWS account ID where Qualys CSPM is activated"

  validation {
    condition     = can(regex("^\\d{12}$", var.qualys_cspm_account))
    error_message = "Must be a valid 12-digit AWS account ID."
  }
}

variable "external_id" {
  type        = string
  description = "External ID for secure cross-account role assumption"
  sensitive   = true
}

variable "qualys_cspm_read_only_role" {
  type        = string
  default     = "qualys-cspm-read-only-role"
  description = "Name of the IAM role Qualys will assume"
}

variable "cloud_type" {
  type    = string
  default = "Commercial"

  validation {
    condition     = contains(["Commercial", "GovCloud", "China"], var.cloud_type)
    error_message = "Must be one of: Commercial, GovCloud, China."
  }
}

variable "qualys_service_type" {
  type    = string
  default = "CSPM"

  validation {
    condition     = contains(["CSPM", "AssetInventory"], var.qualys_service_type)
    error_message = "Must be one of: CSPM, AssetInventory."
  }
}

variable "ou_id" {
  type        = string
  default     = ""
  description = "OU ID (ou-xxxx-xxxxxxxx) or root ID (r-xxxx). Leave empty for current account only."

  # allow empty string, or valid root/OU format
  validation {
    condition = (
      var.ou_id == "" ||
      can(regex("^r-[a-z0-9]{4,32}$", var.ou_id)) ||
      can(regex("^ou-[a-z0-9]{4,32}-[a-z0-9]{8,32}$", var.ou_id))
    )
    error_message = "Must be empty, a root ID like r-abcd, or an OU ID like ou-abcd-12345678."
  }
}

###############################
#  SNAPSHOT SCANNER CONFIG    #
###############################

variable "qualys_subscription_token" {
  type        = string
  sensitive   = true
  description = "Qualys Subscription Token - generate at: https://docs.qualys.com/en/conn/latest/#t=scans%2Fsnapshot-based_scan.htm"
}

variable "qualys_api_gateway_url" {
  type        = string
  default     = "https://gateway.qg1.apps.qualys.com"
  description = "Qualys API Gateway URL - see: https://www.qualys.com/platform-identification/"

  # require HTTPS
  validation {
    condition     = can(regex("^https://[-a-zA-Z0-9@:%._+~#=]{2,256}\\.[a-z]{2,24}\\b([-a-zA-Z0-9@:%_+.~#?&/=]*)$", var.qualys_api_gateway_url))
    error_message = "Must be a valid HTTPS URL."
  }
}

# Allowed regions kept in a local for maintainability
locals {
  allowed_regions = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "af-south-1", "ap-east-1", "ap-south-2", "ap-southeast-3", "ap-southeast-4",
    "ap-south-1", "ap-northeast-3", "ap-northeast-2", "ap-southeast-1",
    "ap-southeast-2", "ap-northeast-1", "ca-central-1", "ca-west-1",
    "eu-central-1", "eu-west-1", "eu-west-2", "eu-south-1", "eu-west-3",
    "eu-south-2", "eu-north-1", "eu-central-2", "il-central-1",
    "me-south-1", "me-central-1", "sa-east-1"
  ]
}

variable "target_regions" {
  type        = set(string)
  default     = ["us-east-1"]
  description = "AWS regions to enable Snapshot scanning"

  validation {
    condition     = length(setsubtract(var.target_regions, local.allowed_regions)) == 0
    error_message = "One or more regions are not supported for Qualys Snapshot Scanner."
  }
}

# Concurrency & Scheduling
variable "single_region_concurrency" {
  type    = number
  default = 10
  validation {
    condition     = var.single_region_concurrency >= 1 && var.single_region_concurrency <= 50
    error_message = "Must be 1–50 scanners per region."
  }
}

variable "concurrency" {
  type    = number
  default = 2
  validation {
    condition     = var.concurrency >= 1 && var.concurrency <= 5
    error_message = "Must scan 1–5 regions concurrently."
  }
}

variable "interval_hours" {
  type    = number
  default = 24
  validation {
    condition     = var.interval_hours >= 24 && var.interval_hours <= 168
    error_message = "Recurring scan interval must be 24–168 hours."
  }
}

variable "events_batch_window" {
  type    = number
  default = 10
  validation {
    condition     = var.events_batch_window >= 5 && var.events_batch_window <= 720
    error_message = "Event batch window must be 5–720 minutes."
  }
}

variable "poll_retry_interval" {
  type    = number
  default = 240
  validation {
    condition     = var.poll_retry_interval >= 15 && var.poll_retry_interval <= 720
    error_message = "Poll retry must be 15–720 minutes."
  }
}

# Scan Features (booleans now)
variable "swca_enabled" {
  type    = bool
  default = false
}

variable "swca_scan_include_dirs" {
  type    = set(string)
  default = []
}
variable "swca_scan_exclude_dirs" {
  type    = set(string)
  default = []
}

variable "swca_scan_timeout" {
  type    = number
  default = 120
  validation {
    condition     = var.swca_scan_timeout >= 10 && var.swca_scan_timeout <= 1200
    error_message = "SwCA timeout must be 10–1200 seconds."
  }
}

variable "secret_scan_enabled" {
  type    = bool
  default = false
}
variable "secret_scan_include_dirs" {
  type    = set(string)
  default = []
}
variable "secret_scan_exclude_dirs" {
  type    = set(string)
  default = []
}

variable "secret_scan_timeout" {
  type    = number
  default = 120
  validation {
    condition     = var.secret_scan_timeout >= 10 && var.secret_scan_timeout <= 1200
    error_message = "Secret scan timeout must be 10–1200 seconds."
  }
}

variable "ami_scan_enabled" {
  type    = bool
  default = false
}
variable "ami_offline_scan_enabled" {
  type    = bool
  default = false
}

variable "scan_sampling_enabled" {
  type    = bool
  default = false
}
variable "sampling_group_scan_percentage" {
  type    = number
  default = 10
  validation {
    condition     = var.sampling_group_scan_percentage >= 1 && var.sampling_group_scan_percentage <= 50
    error_message = "Sampling percentage must be 1–50%."
  }
}

# Instance & Volume Filtering (use sets for dedupe)
variable "must_have_tag_list" {
  type        = set(string)
  default     = []
  description = "tagKey=tagValue pairs — ALL must exist"
}

variable "at_least_one_in_list" {
  type        = set(string)
  default     = []
  description = "tagKey=tagValue pairs — at least ONE must exist"
}

variable "none_in_the_list" {
  type        = set(string)
  default     = []
  description = "Instances with ANY of these tags are EXCLUDED"
}

variable "none_on_volume" {
  type        = set(string)
  default     = []
  description = "Volumes with ANY of these tags are EXCLUDED"
}

###############################
#  NETWORK & API GATEWAY      #
###############################

variable "vpc_cidr" {
  type    = string
  default = "10.10.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid CIDR (e.g., 10.10.0.0/16)."
  }
}

variable "subnet_cidr" {
  type    = string
  default = "10.10.1.0/24"

  validation {
    condition     = can(cidrnetmask(var.subnet_cidr))
    error_message = "subnet_cidr must be a valid CIDR (e.g., 10.10.1.0/24)."
  }
}

###############################
#  TARGET ACCOUNT             #
###############################

variable "event_based_scan" {
  type        = bool
  default     = false
  description = "Enable event-based scans in the target account"
}

###############################
#  TEMPLATE URLS (S3 Paths)   #
###############################

variable "snapshot_assessment_service_template_url" {
  description = "S3 URL for the Snapshot Scanner Service Account CloudFormation template"
  type        = string
  default     = "https://test123tash.s3.us-east-1.amazonaws.com/CloudFormationTemplate_ServiceAccount+(7).json"
}

variable "snapshot_assessment_target_template_url" {
  description = "S3 URL for the Snapshot Scanner Target Account CloudFormation template"
  type        = string
  default     = "https://test123tash.s3.us-east-1.amazonaws.com/CloudFormationTemplate_TargetAccount+(3).json"
}

variable "eventbridge_integration_template_url" {
  description = "S3 URL for the EventBridge integration CloudFormation template"
  type        = string
  default     = "https://test123tash.s3.us-east-1.amazonaws.com/qualys-cloudtrail-log-ingestion-via-eventbridge+(2)+(11)+(1).yml"
}

variable "totalcloud_cspm_role_template_url" {
  description = "S3 URL for TotalCloud CSPM CloudFormation template"
  type        = string
  default     = "https://test123tash.s3.us-east-1.amazonaws.com/cspm.yaml"
}

variable "zero_touch_api_based_assessment_template_url" {
  description = "S3 URL for Zero Touch API Based Assessment CloudFormation template"
  type        = string
  default     = "https://test123tash.s3.us-east-1.amazonaws.com/zero-touch.yaml"
}

variable "guardduty_integration_template_url" {
  description = "S3 URL GuardDuty Integration CloudFormation template"
  type        = string
  default     = "https://test123tash.s3.us-east-1.amazonaws.com/guardduty.yaml"
}
