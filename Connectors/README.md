# Qualys TotalCloud Connectors

Scripts and templates for onboarding cloud accounts into Qualys TotalCloud (CSPM, VM, Asset Inventory).

```
Connectors/
├── AWS/
│   ├── CreateAccountConnectors/   — bulk-create AWS account connectors via Bash
│   ├── Setup/CloudFormation/      — CloudFormation template to provision the IAM role
│   ├── TerraformTemplates/        — Terraform alternative for individual connectors
│   └── UpdateAssetTags/           — update asset tags on existing AWS connectors
│
├── Azure/
│   ├── Setup/                     — Terraform to provision the Azure Service Principal
│   ├── SubscriptionConnector/     — Bash script for subscription-level connector creation
│   ├── TenantConnector/           — full-lifecycle Python tool (recommended for Azure)
│   └── UpdateAssetTags/           — update asset tags on existing Azure connectors
│
├── GCP/
│   └── Setup/
│       ├── EnableCloudAPIs/       — enable required GCP APIs across projects
│       ├── OrgLevelServiceAccount/ — org-level service account + IAM roles
│       └── ProjectLevelConnector/ — project-level connector Terraform
│
└── OCI/
    └── Setup/Terraform/           — OCI tenancy-level connector setup
```

Each subdirectory has its own README with setup steps. Start there.

For Azure, go straight to [`Azure/TenantConnector/`](Azure/TenantConnector/) — it handles discovery, creation, orphan detection, and restore in one tool.
