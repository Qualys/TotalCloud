##############################################################
# Version: Final Review (2025-11-05)
# Author: Yash Jhunjhunwala
##############################################################

locals {
  joined_regions = join(",", var.target_regions)
  common_tags = {
    Project   = "qualys"
    ManagedBy = "terraform"
  }
  # Boolean → String mapping for CloudFormation parameters
  enabled_map = {
    true  = "Enabled"
    false = "Disabled"
  }
}

##############################################################
# CSPM STACK
##############################################################
resource "aws_cloudformation_stack" "cspm" {
  count = var.deploy_totalcloud_cspm_role ? 1 : 0

  name          = "qualys-cspm"
  template_url  = var.totalcloud_cspm_role_template_url
  capabilities  = ["CAPABILITY_NAMED_IAM"]

  parameters = {
    QualysCSPMAccount  = var.qualys_cspm_account
    ExternalId         = var.external_id
    OuId               = var.ou_id
    QualysCSPMRoleName = var.qualys_cspm_read_only_role
    CloudType          = var.cloud_type
    QualysServiceType  = var.qualys_service_type
  }

  lifecycle {
    prevent_destroy = false
  }
}

##############################################################
# ZERO-TOUCH STACK
##############################################################
resource "aws_cloudformation_stack" "zero_touch" {
  count = var.deploy_zero_touch_api_based_assessment ? 1 : 0

  name          = "qualys-zero-touch"
  template_url = var.zero_touch_api_based_assessment_template_url
  capabilities  = ["CAPABILITY_NAMED_IAM"]

  parameters = {
    SubscriptionToken = var.qualys_subscription_token
    APIGatewayURL     = var.qualys_api_gateway_url
    Regions           = local.joined_regions
  }
}

##############################################################
# GUARDDUTY STACK
##############################################################
resource "aws_cloudformation_stack" "guardduty" {
  count = var.deploy_guardduty_integration ? 1 : 0

  name          = "qualys-guardduty"
  template_url = var.guardduty_integration_template_url
  capabilities  = ["CAPABILITY_NAMED_IAM"]

  parameters = {
    SubscriptionToken = var.qualys_subscription_token
    APIGatewayURL     = var.qualys_api_gateway_url
    Regions           = local.joined_regions
  }
}

##############################################################
# SNAPSHOT SCANNER - SERVICE ACCOUNT STACK
##############################################################
resource "aws_cloudformation_stack" "snapshot_scanner" {
  count = var.deploy_service_account_for_snapshot_assessment ? 1 : 0

  name               = "qualys-snapshot-scanner"
  template_url       = var.snapshot_assessment_service_template_url
  capabilities       = ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND"]
  timeout_in_minutes = 30

  parameters = {
    QToken                  = var.qualys_subscription_token
    QEndpoint               = var.qualys_api_gateway_url
    Regions                 = local.joined_regions
    SingleRegionConcurrency = var.single_region_concurrency
    Concurrency             = var.concurrency
    IntervalHours           = var.interval_hours
    EventsBatchWindow       = var.events_batch_window
    PollRetryInterval       = var.poll_retry_interval

    # Boolean → String conversions
    SwCA           = local.enabled_map[var.swca_enabled]
    Secret         = local.enabled_map[var.secret_scan_enabled]
    AMI            = local.enabled_map[var.ami_scan_enabled]
    AMIOfflineScan = local.enabled_map[var.ami_offline_scan_enabled]
    ScanSampling   = local.enabled_map[var.scan_sampling_enabled]

    # Lists & numeric params
    SwCAScanIncludeDirs         = join(",", var.swca_scan_include_dirs)
    SwCAScanExcludeDirs         = join(",", var.swca_scan_exclude_dirs)
    SwCAScanTimeout             = var.swca_scan_timeout
    SecretScanIncludeDirs       = join(",", var.secret_scan_include_dirs)
    SecretScanExcludeDirs       = join(",", var.secret_scan_exclude_dirs)
    SecretScanTimeout           = var.secret_scan_timeout
    SamplingGroupScanPercentage = var.sampling_group_scan_percentage
    MustHaveTagList             = join(",", var.must_have_tag_list)
    AtLeastOneInList            = join(",", var.at_least_one_in_list)
    NoneInTheList               = join(",", var.none_in_the_list)
    NoneOnVolume                = join(",", var.none_on_volume)
  }

  lifecycle {
    prevent_destroy = false
  }
}

##############################################################
# SNAPSHOT SCANNER TARGET STACK
##############################################################
resource "aws_cloudformation_stack" "snapshot_scanner_target" {
  count = var.deploy_target_account_for_snapshot_assessment ? 1 : 0

  name               = "qualys-snapshot-target"
  template_url       = var.snapshot_assessment_target_template_url
  capabilities       = ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND"]
  timeout_in_minutes = 30

  parameters = {
    QToken                 = var.qualys_subscription_token
    ServiceAccount         = data.aws_caller_identity.current.account_id
    APIDestinationEndpoint = try(aws_cloudformation_stack.snapshot_scanner[0].outputs["AGProxyApiEndpoint"], "")
    TargetRegions          = local.joined_regions
    EventBasedScan         = local.enabled_map[var.event_based_scan]
  }

  depends_on = [aws_cloudformation_stack.snapshot_scanner]

  lifecycle {
    prevent_destroy = false
  }
}

##############################################################
# EVENTBRIDGE INTEGRATION STACK
##############################################################
resource "aws_cloudformation_stack" "eventbridge_integration" {
  count = var.deploy_eventbridge_integration ? 1 : 0

  name         = "qualys-event-bridge"
  template_url = var.eventbridge_integration_template_url
  capabilities = ["CAPABILITY_NAMED_IAM"]

  parameters = {
    SubscriptionToken = var.qualys_subscription_token
    APIGatewayURL     = var.qualys_api_gateway_url
    Regions           = local.joined_regions
  }
}
