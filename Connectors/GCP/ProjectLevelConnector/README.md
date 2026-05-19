# GCP Project-Level Connector Setup

Terraform configuration to create a Qualys service account and enable required GCP APIs at the **project level**. Use this when you want to connect a single GCP project rather than your entire organization.

For org-wide onboarding, use [`../OrgLevelServiceAccount/`](../OrgLevelServiceAccount/) instead.

## What it does

- Enables 14 required GCP APIs in the specified project
- Creates a `QualysCSPMServiceAccount` service account
- Assigns `roles/viewer` and `roles/iam.securityReviewer` at project scope
- Generates a service account key and saves it to `key.json`

## Prerequisites

- GCP project with Owner or Editor permissions
- Terraform 1.0+ installed, or use Google Cloud Shell

## Steps

```bash
git clone https://github.com/Qualys/TotalCloud.git
cd TotalCloud/Connectors/GCP/ProjectLevelConnector/Terraform
```

1. Edit `terraform.tfvars` with your project ID:
   ```hcl
   project_id = "your-gcp-project-id"
   ```

2. Authenticate with GCP:
   ```bash
   gcloud auth application-default login
   ```

3. Run Terraform:
   ```bash
   terraform init
   terraform plan
   terraform apply
   ```

4. Use the generated `key.json` to configure the connector in the Qualys portal.

## Outputs

| Output | Description |
|--------|-------------|
| `service_account_email` | Email of the created service account |
| `api_keys_json` | JSON key for the service account (sensitive) |
| `project_id` | The GCP project ID |

## Security Note

Keep `key.json` secure — it grants read access to your GCP project. Do not commit it to version control.

## Author
Yash Jhunjhunwala, Lead SME Cloud Security Solutions
