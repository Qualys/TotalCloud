# 📘 Qualys TotalCloud – AWS Unified Terraform Deployment  (

---

## 🚀 Overview

This repository provides a **complete, Terraform deployment** for Qualys TotalCloud integrations on AWS:

- **CSPM (Cloud Security Posture Management) - Connectors**
- **Zero-Touch API Based Assessment**
- **GuardDuty Event Ingestion**
- **Zero-Touch Snapshot Assessment (Service Account)**
- **Zero-Touch Snapshot Assessmentr (Target Account)**
- **Cloud Trail EventBridge Integration(Delete Events)**


---

## 📁 Repository Structure

```
.
├── main.tf
├── provider.tf
├── variables.tf
├── outputs.tf
├── terraform.tfvars
└── templates/
    ├── cspm.yaml
    ├── zero-touch.yaml
    ├── guardduty.yaml
    ├── snapshot-scanner.json
    └── snapshot-scanner-target.json
```

---

# 🛠️ 1. Prerequisites

Before deploying, ensure you have the following:

### ✔ Terraform ≥ 1.5  
### ✔ AWS CLI installed  
### ✔ AWS account permissions:
- AdministratorAccess

### ✔ Configure AWS profile  
```bash
aws configure --profile <your-profile>
```


# ✏️ 2. Configure terraform.tfvars

Update this file before deployment.

### 🔑 Required Values

```hcl
qualys_subscription_token = "<PASTE-TOKEN>"
qualys_api_gateway_url    = "<https://gateway.qg1.apps.qualys.com>"

qualys_cspm_account = "<QUALYS-AWS-ACCOUNT>"
external_id         = "<EXTERNAL-ID-GIVEN-BY-QUALYS>"
```

### 🌎 Regions for Deployment (multi-region EventBridge)

```hcl
eb_regions = [
  "us-east-1",
  "us-west-2",
  "us-west-1",
  "us-east-2"
]
```

### 🏛 OU ID for multi-account deployment

If using AWS Organizations:

```hcl
ou_id = "ou-xxxx-xxxxxxxx"
```

Leave empty for single-account:

```hcl
ou_id = ""
```

### 🔧 Enable/Disable Integrations

```hcl
deploy_cspm                    = true
deploy_zero_touch              = true
deploy_guardduty               = true
deploy_snapshot_scanner        = true
deploy_snapshot_scanner_target = true
deploy_eventbridge_integration = true
```

---

# 🚀 4. Deployment Steps

### **Step 1 – Initialize Terraform**
```bash
terraform init
```

### **Step 2 – Validate Configuration**
```bash
terraform validate
```

### **Step 3 – Review Deployment Plan**
```bash
terraform plan -var="aws_profile=<your-profile>"
```

### **Step 4 – Apply Deployment**
```bash
terraform apply -var="aws_profile=<your-profile>"
```

Terraform will deploy:

- CSPM (Cloud Security Posture Management) - Connectors
- Zero-Touch API Based Assessment
- GuardDuty Event Ingestion
- Zero-Touch Snapshot Assessment (Service Account)
- Zero-Touch Snapshot Assessmentr (Target Account)
- Cloud Trail EventBridge Integration(Delete Events)

Deployment takes **3–6 minutes**.

---

# 📤 5. Post-Deployment: Connect Your AWS Account to Qualys

Terraform will output:

- CSPM Role ARN  
- Snapshot Scanner API Endpoint  
- AWS Account ID  
- Zero Touch deployment status  
- GuardDuty deployment status  
- **One-line connector setup string**

Example:

```
qualys_console_paste_this =
API URL: https://abcd123.qualys.com/scan | Account ID: 123456789012
```

Paste this into:

**Qualys Cloud → Connectors → AWS → Add Account**
