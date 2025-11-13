# ───────────────────────────────────────────────────────────────
#  terraform.tfvars – JUST SAVE THIS FILE IN YOUR PROJECT ROOT
# ───────────────────────────────────────────────────────────────
#AWS_PROFILE=prod terraform apply

# DEPLOYMENT TOGGLES
deploy_totalcloud_cspm_role                         = true
deploy_zero_touch_api_based_assessment              = true
deploy_service_account_for_snapshot_assessment      = true
deploy_target_account_for_snapshot_assessment       = true
deploy_guardduty_integration                        = true
deploy_eventbridge_integration                      = true

# Deployment Templates
totalcloud_cspm_role_template_url                   = ""
zero_touch_api_based_assessment_template_url        = ""
snapshot_assessment_service_template_url            = ""
snapshot_assessment_target_template_url             = ""
guardduty_integration_template_url                  = ""
eventbridge_integration_template_url                = ""


# QUALYS AUTH
qualys_subscription_token = ""
qualys_api_gateway_url = "" # Refer https://www.qualys.com/platform-identification/

# CSPM SETTINGS (change only if you know what you’re doing)
qualys_cspm_account        = "805950163170" # Base Account Details, You can get this from Qualys Platform
external_id                = "qualys-sso-2025" # CHANGE THIS to anything unique
qualys_cspm_read_only_role = "qualys-cspm-read-only-role"
cloud_type                 = "Commercial" # Allowed Values Commercial, GovCloud, China
qualys_service_type        = "CSPM" # Allowed Values CSPM, AssetInventory
ou_id                      = "" # OU ID (ou-xxxx-xxxxxxxx) or root ID (r-xxxx). Leave empty for single account deployment

# REGIONS
target_regions = ["us-east-1", "us-east-2", "us-west-1", "us-west-2"]
/* [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "af-south-1", "ap-east-1", "ap-south-2", "ap-southeast-3", "ap-southeast-4",
    "ap-south-1", "ap-northeast-3", "ap-northeast-2", "ap-southeast-1",
    "ap-southeast-2", "ap-northeast-1", "ca-central-1", "ca-west-1",
    "eu-central-1", "eu-west-1", "eu-west-2", "eu-south-1", "eu-west-3",
    "eu-south-2", "eu-north-1", "eu-central-2", "il-central-1",
    "me-south-1", "me-central-1", "sa-east-1"
  ] */

# SNAPSHOT SCANNER SETTINGS (defaults = safe & fast)
single_region_concurrency = 10
concurrency               = 2
interval_hours            = 24
events_batch_window       = 10
poll_retry_interval       = 240

# SCAN FEATURES
swca_enabled           = true
swca_scan_include_dirs = []
swca_scan_exclude_dirs = []
swca_scan_timeout      = 120

secret_scan_enabled      = true
secret_scan_include_dirs = []
secret_scan_exclude_dirs = []
secret_scan_timeout      = 120

ami_scan_enabled               = true
ami_offline_scan_enabled       = true
scan_sampling_enabled          = false
sampling_group_scan_percentage = 10

# TAG FILTERS
must_have_tag_list   = []
at_least_one_in_list = []
none_in_the_list     = []
none_on_volume       = []

# NETWORK (leave default)
vpc_cidr    = "10.10.0.0/16"
subnet_cidr = "10.10.1.0/24"

# Target Account SETTINGS (defaults = safe & fast)
event_based_scan = true

