# Qualys TotalCloud – Unified AWS Terraform Deployment
### Deployment Guide for CSPM, Zero-Touch, Snapshot Scanner, GuardDuty and EventBridge

This repository contains a Terraform-based framework that deploys all required Qualys TotalCloud components in AWS. The goal is to provide a single, consistent deployment method for:

- CSPM cross-account IAM role
- Zero-Touch API-based assessment
- Snapshot Scanner (Service Account)
- Snapshot Scanner (Target Account)
- GuardDuty findings integration
- EventBridge multi-region forwarding

All configurations are controlled through `terraform.tfvars` and `variables.tf`.

---

## Repository Structure

```
.
├── main.tf
├── variables.tf
├── provider.tf
├── outputs.tf
├── terraform.tfvars
└── README.md
```

CloudFormation templates are referenced using S3 URLs (not stored locally).

---

## 1. Prerequisites

Before deploying, ensure you have:

- Terraform v1.3 or later  
- AWS CLI v2  
- IAM permissions that allow:  
  - CloudFormation (Stacks and StackSets)  
  - IAM role/policy management  
  - EventBridge resources (rules, connections, API destinations)  
  - Reading CloudFormation templates from S3  

Configure AWS CLI:

```bash
aws configure --profile <your-aws-profile>
```

---

## 2. Configuring `terraform.tfvars`

Below is an explanation of each variable defined in `variables.tf`. Update values as required before deployment.

---

### Deployment Toggles

Enable or disable individual components:

```hcl
deploy_totalcloud_cspm_role                         = true
deploy_zero_touch_api_based_assessment              = true
deploy_service_account_for_snapshot_assessment      = true
deploy_target_account_for_snapshot_assessment       = true
deploy_guardduty_integration                        = true
deploy_eventbridge_integration                      = true
```

| Variable | Description |
|----------|-------------|
| `deploy_totalcloud_cspm_role` | Deploy CSPM IAM Cross-Account Role |
| `deploy_zero_touch_api_based_assessment` | Deploy Zero-Touch EventBridge + API Destination |
| `deploy_service_account_for_snapshot_assessment` | Deploy Snapshot Scanner Service Account |
| `deploy_target_account_for_snapshot_assessment` | Deploy Snapshot Target Account |
| `deploy_guardduty_integration` | Deploy GuardDuty → Qualys forwarding |
| `deploy_eventbridge_integration` | Deploy Multi-Region EventBridge replication |

---

### Qualys Authentication

```hcl
qualys_subscription_token = "<paste-token>"
qualys_api_gateway_url    = "https://gateway.qg1.apps.qualys.com"
```

| Variable | Description |
|----------|-------------|
| `qualys_subscription_token` | Subscription token from Qualys Console |
| `qualys_api_gateway_url` | API Gateway URL (refer platform identification page) |

---

### CSPM Cross-Account Role Settings

```hcl
qualys_cspm_account        = "805950163170"
external_id                = "qualys-sso-2025"
qualys_cspm_read_only_role = "qualys-cspm-read-only-role"
cloud_type                 = "Commercial"
qualys_service_type        = "CSPM"
ou_id                      = ""
```

| Variable | Description |
|----------|-------------|
| `qualys_cspm_account` | Qualys AWS account used to assume roles |
| `external_id` | Mandatory external ID for secure assume-role |
| `qualys_cspm_read_only_role` | IAM role name created in accounts |
| `cloud_type` | Allowed: `Commercial`, `GovCloud`, `China` |
| `qualys_service_type` | Allowed: `CSPM`, `AssetInventory` |
| `ou_id` | OU ID for Org-wide deployment (leave blank for single account) |

---
### Region Selection

```hcl
target_regions = ["us-east-1", "us-east-2", "us-west-1", "us-west-2"]
```

These regions are used for:

- Zero-Touch  
- GuardDuty integration  
- EventBridge rules  
- Multi-region forwarding  
- Snapshot Scanner (Target Account)  

Supported regions are validated in `variables.tf`.

---

### Snapshot Based Assessmnet Service Account Settings

```hcl
single_region_concurrency = 10
concurrency               = 2
interval_hours            = 24
events_batch_window       = 10
poll_retry_interval       = 240
```

| Variable | Description |
|----------|-------------|
| `single_region_concurrency` | Scanner threads per region (1–50) |
| `concurrency` | Regions scanned in parallel (1–5) |
| `interval_hours` | Scheduled scan interval (24–168 hrs) |
| `events_batch_window` | EventBridge buffer window (5–720 mins) |
| `poll_retry_interval` | Retry interval (15–720 mins) |

---

### Scan Feature Toggles

```hcl
swca_enabled                 = true
secret_scan_enabled          = true
ami_scan_enabled             = true
ami_offline_scan_enabled     = true
scan_sampling_enabled        = false
sampling_group_scan_percentage = 10
```

| Variable | Description |
|----------|-------------|
| `swca_enabled` | Enable Software Composition Analysis |
| `secret_scan_enabled` | Scan secrets in snapshots |
| `ami_scan_enabled` | Enable AMI scanning |
| `ami_offline_scan_enabled` | Offline AMI delta scan |
| `scan_sampling_enabled` | Enable sampling mode |
| `sampling_group_scan_percentage` | % of instances to sample |

---

### Tag-Based Filtering

```hcl
must_have_tag_list   = []
at_least_one_in_list = []
none_in_the_list     = []
none_on_volume       = []
```

| Variable | Description |
|----------|-------------|
| `must_have_tag_list` | Instance must contain **ALL** tagKey=tagValue pairs |
| `at_least_one_in_list` | Instance must contain **ANY** listed tag |
| `none_in_the_list` | Exclude instances with these tags |
| `none_on_volume` | Exclude volumes with these tags |

---

### Network Configuration

```hcl
vpc_cidr    = "10.10.0.0/16"
subnet_cidr = "10.10.1.0/24"
```

| Variable | Description |
|----------|-------------|
| `vpc_cidr` | CIDR block for scanner VPC |
| `subnet_cidr` | CIDR block for scanner subnet |

---

### Target Account Settings

```hcl
event_based_scan = true
```

Enables EC2-event driven snapshot assessment in the **target** AWS accounts.

---

### CloudFormation Template URLs (S3)

```hcl
totalcloud_cspm_role_template_url              = "https://bucket/cspm.yaml"
zero_touch_api_based_assessment_template_url   = "https://bucket/zero-touch.yaml"
snapshot_assessment_service_template_url       = "https://bucket/service.json"
snapshot_assessment_target_template_url        = "https://bucket/target.json"
guardduty_integration_template_url             = "https://bucket/guardduty.yaml"
eventbridge_integration_template_url           = "https://bucket/eventbridge.yml"
```

Each URL must point to a valid S3 object containing a CloudFormation template.

---

## 3. Deployment Steps

### 1. Initialize
```bash
terraform init
```

### 2. Validate
```bash
terraform validate
```

### 3. Preview Changes
```bash
terraform plan -var="aws_profile=prod"
```

### 4. Deploy
```bash
terraform apply -var="aws_profile=prod"
```

---

## 4. Outputs

Terraform prints:

- CSPM Role ARN  
- Snapshot Service API URL  
- AWS Account ID  
- Status of each integration  
- A **copy-paste string** for the Qualys Console  

Paste into:  
**Qualys → TotalCloud → Connectors → Add AWS Account**

---

## Author

**Author:** *Yash Jhunjhunwala (Lead SME, Cloud Security)*  
**Project:** Qualys TotalCloud Unified Terraform Deployment  
**Last Updated:** 2025-11  
