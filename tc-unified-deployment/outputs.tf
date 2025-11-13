##############################################
#  QUALYS OUTPUTS – PRODUCTION SAFE VERSION  #
##############################################

# Ensure AWS account info is available
data "aws_caller_identity" "current" {}

# ───────────────────────────────────────────────
# CSPM
# ───────────────────────────────────────────────
output "qualys_cspm_role_arn" {
  description = "IAM Role Qualys CSPM will assume"
  value       = var.deploy_totalcloud_cspm_role ? try(aws_cloudformation_stack.cspm[0].outputs["RoleARN"], "CSPM role output not available") : "CSPM not deployed"
}

# ───────────────────────────────────────────────
# Zero Touch
# ───────────────────────────────────────────────
output "zero_touch_status" {
  description = "Deployment status of the Zero-Touch connector"
  value       = var.deploy_zero_touch_api_based_assessment ? "DEPLOYED" : "SKIPPED"
}

# ───────────────────────────────────────────────
# GuardDuty
# ───────────────────────────────────────────────
output "guardduty_status" {
  description = "Deployment status of the GuardDuty integration"
  value       = var.deploy_guardduty_integration ? "DEPLOYED" : "SKIPPED"
}

# ───────────────────────────────────────────────
# Snapshot Scanner (Service Account)
# ───────────────────────────────────────────────
output "snapshot_scanner_api" {
  description = "API Gateway URL – paste into Qualys Console"
  value       = var.deploy_service_account_for_snapshot_assessment ? try(aws_cloudformation_stack.snapshot_scanner[0].outputs["AGProxyApiEndpoint"], "Endpoint not found") : "Not deployed"
}

output "snapshot_scanner_aws_account_id" {
  description = "AWS Account ID – paste into Qualys Console"
  value       = var.deploy_service_account_for_snapshot_assessment ? data.aws_caller_identity.current.account_id : "N/A"
}

# ───────────────────────────────────────────────
# Snapshot Scanner (Target Account)
# ───────────────────────────────────────────────
output "snapshot_scanner_target_status" {
  description = "Deployment status of the Snapshot Scanner Target Account"
  value       = var.deploy_target_account_for_snapshot_assessment ? "DEPLOYED" : "SKIPPED"
}

# ───────────────────────────────────────────────
# One-line Console Copy for Qualys UI
# ───────────────────────────────────────────────
output "qualys_console_paste_this" {
  description = "COPY this → PASTE into Qualys Console → Connectors → Add AWS Account"
  value = var.deploy_service_account_for_snapshot_assessment ? format(
    "API URL: %s | Account ID: %s",
    try(aws_cloudformation_stack.snapshot_scanner[0].outputs["AGProxyApiEndpoint"], "unknown"),
    data.aws_caller_identity.current.account_id
  ) : "Snapshot Scanner not deployed"
}
