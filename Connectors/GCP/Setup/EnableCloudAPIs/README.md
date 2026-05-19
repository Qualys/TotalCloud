# Enable Google Cloud APIs on All Projects within an Organization using Terraform

This Terraform configuration enables specified Google Cloud APIs on all projects within a Google Cloud organization.

## Prerequisites

Before you begin, make sure you have the following prerequisites:

- Google Cloud Platform account and authentication credentials.
- Terraform installed on your local machine.

## Permissions

To execute the above Terraform script to enable Google Cloud APIs on projects within an organization, you need the following permissions:

- Google Cloud Organization Admin: You should have administrative access to the Google Cloud Organization to manage projects and enable APIs. The role required is typically roles/resourcemanager.organizationAdmin or equivalent custom roles with the necessary permissions.

- Service Usage Admin: To enable and disable APIs, you need the roles/serviceusage.serviceUsageAdmin or equivalent custom roles. This role allows you to manage the service usage of APIs.

Please note that these are the broad roles required, and you may need additional roles depending on your specific setup and security policies. Ensure that you follow your organization's security and access control policies when granting permissions. It's a good practice to use the principle of least privilege, granting only the minimum required permissions to each user or service account.

## Steps

### 1. Set Up Your Terraform Configuration

Start by creating a Terraform configuration to manage the projects within your organization. Ensure you have set up the necessary authentication and provider configuration.
provider.tf

```hcl
provider "google"{
}
```
### 2. Retrieve the List of Projects

Use the Google Cloud CLI or a programming language (e.g., Python) to fetch a list of all projects within your organization. You can use the following gcloud command:
```shell
gcloud projects list --format="value(projectId)" > project_ids.txt
```
To Check Count of Projects
```shell
sort project_ids.txt | uniq | wc -l
```
 
This command saves the list of project IDs to a text file, project_ids.txt.

### 3. Iterate Over the Project IDs
In your Terraform configuration, use a for_each loop to iterate over the project IDs.

# Read project IDs from a text file
```hcl
variable "project_ids_file" {
  default = "project_ids.txt"
}

locals {
  project_ids = split("\n", file(var.project_ids_file))
}
```

### 4. Enable Google Cloud APIs

Use the google_project_service resource within the loop to enable the required APIs for each project.

Here's an example of enabling specific APIs, such as Compute Engine and Cloud Resource Manager APIs:
```hcl
# Enable Compute Engine API
resource "google_project_service" "compute_engine" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "compute.googleapis.com"
  # Additional configurations, if needed
}

# Enable Cloud Resource Manager API
resource "google_project_service" "cloud_resource_manager" {
  for_each = { for idx, project_id in local.project_ids : idx => project_id }
  project = each.value
  service = "cloudresourcemanager.googleapis.com"
  # Additional configurations, if needed
}
```

### 5. Execute Terraform
Run terraform init and terraform apply to execute the Terraform configuration.

Please ensure that you have the necessary permissions to enable services for the projects within your organization. Also, use this Terraform configuration with caution, as enabling or disabling services can impact project functionality.
