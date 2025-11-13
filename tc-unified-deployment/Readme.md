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

- CSPM IAM Role + optional StackSet to OU
- Zero-Touch EventBridge stack
- GuardDuty EventBridge stack
- Snapshot Scanner (Service Account)
- Snapshot Scanner (Target Account)
- Multi-region forwarding rules

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

---

# 🌎 6. Multi-Region Architecture

This deployment uses EventBridge + StackSets:

### **Primary Region (e.g., us-east-1):**
- API Destinations  
- Main EventBridge rule  
- Snapshot Scanner Service Account  

### **Secondary Regions:**
- EventBridge rules forward events  
- Events sent to primary region  
- Zero-Touch & GuardDuty events centralized  

Regions are controlled by:

```hcl
eb_regions = [...]
```

---

# 🛡️ 7. Security Architecture

### ✔ IAM Roles use ExternalId  
Prevents unauthorized cross-account access.

### ✔ CloudFormation templates are partition-aware  
Works in:
- aws  
- aws-us-gov  
- aws-cn  

### ✔ Prevent Destroy disabled  
Allows safe upgrades.

### ✔ All roles/resources prefixed with `qualys-`  
Matches recommended naming conventions.

### ✔ No secrets stored in Terraform output  
Subscription token is marked `sensitive = true`.

---

# 🧹 8. Cleanup

Run:

```bash
terraform destroy -var="aws_profile=<your-profile>"
```

AWS StackSets will automatically remove:

- Cross-region EventBridge rules  
- Target Account roles  
- All Qualys stacks  

---

# 🩺 9. Troubleshooting

### ❗ **Error: “Role already exists”**
IAM role names are global per account.  
Delete older roles from IAM console and re-run.

---

### ❗ **No events arriving in Qualys**
Check:

- EventBridge → Rules (ensure “qualys-*” rules are enabled)
- EventBridge → Connections (should show “Healthy”)
- IAM role trust policy (must allow `events.amazonaws.com`)
- Security groups/VPC endpoints if GovCloud/China

---

### ❗ **CloudFormation stuck in REVIEW_IN_PROGRESS**
Re-run `terraform apply`.  
CloudFormation auto-resolves dependent stacks.

---

# 🧭 10. Support

📄 Qualys Documentation  
https://docs.qualys.com/

📞 Qualys Support  
https://www.qualys.com/support/

☁️ AWS Support  
https://docs.aws.amazon.com/

---

# 🎉 You're All Set!

You now have a **complete, production-ready deployment pipeline** for all Qualys TotalCloud AWS integrations using Terraform:

- CSPM  
- Zero-Touch  
- GuardDuty  
- Snapshot Scanner  
- EventBridge Multi-Region Routing  

If you need:
- Architecture diagram  
- Quick Start PDF for customers  
- Slides for internal enablement  
- Versioned CHANGELOG.md  

Just ask!
