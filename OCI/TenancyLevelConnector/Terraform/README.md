# OCI IAM User and API Key Setup with Terraform

This repository contains Terraform configuration files to create an IAM user, IAM group, policy, and API key in Oracle Cloud Infrastructure (OCI). The setup is performed at the tenancy level for simplicity.

## Prerequisites

- [Terraform](https://www.terraform.io/downloads) installed (version 1.0.0 or later).
- OCI CLI configured with necessary permissions.
- Access to OCI Tenancy OCID and region information.

## Repository Structure

- **`main.tf`**: Contains resource definitions for IAM user, group, policy, and API key.
- **`outputs.tf`**: Defines output values.
- **`variables.tf`**: Declares input variables.
- **`provider.tf`**: Configures the OCI provider.
- **`terraform.tfvars`**: Contains variable values for deployment.

## Configuration

1. **Clone the Repository**
   ```bash
   git clone https://github.com/Qualys/TotalCloud.git
   cd OCI/TenancyLevelConnector/Terraform/

2. **Update terraform.tfvars** :
- Edit the terraform.tfvars file with your OCI details:
   ```bash
   home_region     = "us-ashburn-1"  # Update with your OCI region
   tenancy_id       = "ocid1.tenancy.oc1..aaaaaaaax2gwhq3hasgdahkdasdgasdar6kxn7itgkasdwhk7keokamq"  # Update with your Tenancy OCID

3. **Initialize Terraform** :
- Initialize your Terraform workspace to download the required providers:
   ```bash
   terraform init

4. **Plan the Deployment** :
- Review the execution plan to ensure it meets your requirements:
   ```bash
   terraform plan

5. **Apply the Configuration** :
- Deploy the configuration to OCI:
   ```bash
   terraform apply 
- Confirm the action when prompted.

6. **Verify Outputs** :
- Review the execution plan to ensure it meets your requirements:
- After applying the configuration, Terraform will output important information such as:
  - Tenant OCID
  - User OCID
  - Region
  - Path to the generated private key
  - API key fingerprint
 
## Cleanup
To remove the resources created by this Terraform configuration, run:
   ```bash
   terraform destroy 
```
## Notes
- `Security`: Ensure that the private key file (oci_api_key.pem) is handled securely and not committed to version control.
- `Permissions`: The user running Terraform needs sufficient permissions to create IAM users, groups, policies, and API keys in the OCI tenancy.
