# Create a service account, and assigns IAM roles at the organization level

This Terraform script enables various Google Cloud APIs for multiple projects within an organization, creates a service account, and assigns IAM roles at the organization level. Use this script with caution and ensure you have the necessary permissions before execution.

## Prerequisites

Before you begin, make sure you have the following:

- A Google Cloud Organization with the necessary permissions to manage projects and IAM roles.
- Terraform installed on your local machine.
- Google Cloud credentials with appropriate permissions.

## Steps

Follow these steps to use the Terraform script:

1. Clone the Repository:
```bash
git clone https://github.com/Qualys/TotalCloud.git
cd TotalCloud/GCP/Create_Service_Account_For_Org_Connector
```
2. Configure Terraform:

Set up your Google Cloud credentials and configure the provider "google" block in the Terraform script.
```bash
provider "google" {
  credentials = file("path/to/your/credentials.json")
}
```
3. Define Variables: Update the variables in the script according to your requirements. Ensure you set the correct project_id and organization_id.

4. Run Terraform: Initialize Terraform and apply the configuration.
```bash
terraform init
terraform apply
```
Terraform will prompt you to confirm the changes.

Review Outputs: After successful execution, Terraform will provide outputs, including the JSON key for the created service account.

Cleanup (Optional): If needed, you can destroy the created resources.
```bash
terraform destroy
```
## Permissions 

To successfully run this Terraform script, you must have the following permissions:

- Project-level permissions for enabling APIs:
  - roles/editor or equivalent.
- Organization-level permissions for managing IAM roles and bindings:
  - roles/resourcemanager.organizationAdmin or equivalent.
  - roles/iam.organizationRoleAdmin or equivalent.

##  Important Notes
Be cautious when running scripts that modify IAM roles and API access, as they can have a significant impact on your organization's security and resources.
