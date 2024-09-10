# Terraform Configuration for Enabling GCP Services and Creating a Service Account

This zip file contains Terraform configuration files to enable various Google Cloud Platform (GCP) services, create a service account, and assign necessary roles to the service account.

## Prerequisites

- Google Cloud Platform account with necessary permissions
- Google Cloud Shell access or Googgle CLI

## Setup

This solution can be deployed from Google Cloudshell or Google CLI

1. **Download Terraform connector zip file totalcloud_gcp.zip

    - (Optional)If use Google Cloudshell to deploy the solution, upload the zip file to Google Cloudshell
    - unzip totalcloud_gcp.zip
    - cd totalcloud_gcp

2. Initialize Terraform:
   ```sh
   terraform init

3. Plan the changes:
   ```sh
   terraform plan

4. Apply the changes:
   ```sh
   terraform apply

Enter `yes` when prompted to confirm.

## Files and Configuration
`main.tf`
This file contains the main Terraform configuration including:

- Enabling GCP services:
  - Compute Engine
  - Cloud Resource Manager
  - Kubernetes Engine
  - Cloud SQL Admin
  - BigQuery
  - Cloud Functions
  - Cloud DNS
  - Cloud Key Management Service (KMS)
  - Cloud Logging
  - Stackdriver Monitoring
  - Identity and Access Management (IAM)
  - Cloud Pub/Sub
  - Service Usage
  - Cloud Dataproc


- Creating a service account named QualysCSPMServiceAccount.

- Assigning roles (roles/viewer and roles/iam.securityReviewer) to the service account.

- Creating an API key for the service account and saving it to a local file key.json.

`variables.tf`
This file defines the variables used in the configuration:

- `project_id`: The ID of the GCP project.
- `service_account_id`: The ID of the service account (default: qualyscspmserviceaccount).

`outputs.tf`
This file defines the outputs of the Terraform configuration:

- `api_keys_json`: The JSON key for the created service account (marked as sensitive).
- `service_account_email`: The email of the created service account.
- `project_id`: The ID of the GCP project.

`provider.tf`
This file configures the GCP provider for Terraform:

- Specifies the GCP project ID.
- Optionally, specify the region if required.
- Credentials can be provided via environment variables or directly in the configuration.

`Outputs`
- `api_keys_json`: The JSON key for the created service account (sensitive).
- `service_account_email`: The email of the created service account.
- `project_id`: The ID of the GCP project.

## Notes
Ensure that the service account key (key.json) is securely stored and managed.
Modify the provider configuration in provider.tf as needed for your environment.
Always review the plan (terraform plan) before applying (terraform apply) to understand the changes that will be made to your infrastructure.
