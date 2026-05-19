# Qualys TotalCloud Connectors

Scripts and templates for onboarding cloud accounts into Qualys TotalCloud (CSPM, VM, Asset Inventory).

```
Connectors/
├── AWS/
│   ├── CloudFormation/            — CloudFormation template to provision the IAM role
│   ├── TerraformTemplates/        — Terraform alternative for individual connectors
│   ├── CreateAccountConnectors/   — bulk-create AWS account connectors via Bash
│   └── UpdateAssetTags/           — update asset tags on existing AWS connectors
│
├── Azure/
│   ├── Terraform/                 — Terraform to provision the Azure Service Principal
│   ├── SubscriptionConnector/     — Bash script for subscription-level connector creation
│   ├── TenantConnector/           — full-lifecycle Python tool (recommended for Azure)
│   └── UpdateAssetTags/           — update asset tags on existing Azure connectors
│
├── GCP/
│   ├── EnableCloudAPIs/           — enable required GCP APIs across projects
│   ├── OrgLevelServiceAccount/    — org-level service account + IAM roles
│   └── ProjectLevelConnector/     — project-level connector Terraform
│
└── OCI/
    └── Terraform/                 — OCI tenancy-level connector setup
```

Each subdirectory has its own README with setup steps. Start there.

For Azure, go straight to [`Azure/TenantConnector/`](Azure/TenantConnector/) — it handles discovery, creation, orphan detection, and restore in one tool.

## Author
Yash Jhunjhunwala, Lead SME Cloud Security Solutions
