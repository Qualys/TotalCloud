# AWS Connectors

Tools for onboarding AWS accounts into Qualys TotalCloud.

**[`Setup/CloudFormation/`](Setup/CloudFormation/)** — CloudFormation template that creates the IAM role and policy Qualys needs. Supports single-account deployment or multi-account via StackSets (for AWS Organizations). Covers Commercial, GovCloud, and China regions. Start here if you haven't provisioned the IAM role yet.

**[`TerraformTemplates/`](TerraformTemplates/)** — Terraform alternative to the CloudFormation template for teams already using Terraform for IAM management.

**[`CreateAccountConnectors/`](CreateAccountConnectors/)** — Bash script to bulk-create Qualys connectors once IAM roles are in place. Reads from a CSV, calls the Qualys API for each account.

**[`UpdateAssetTags/`](UpdateAssetTags/)** — Python script to update asset tags on existing AWS connectors.

---

Typical flow: deploy IAM role via CloudFormation → create connector in Qualys portal (or use `CreateAccountConnectors/` for bulk).
