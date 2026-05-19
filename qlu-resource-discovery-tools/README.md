# Qualys Cloud Resource Count Scripts

Python scripts that enumerate and count cloud resources across AWS, Azure, GCP, and OCI for Qualys licensing and inventory purposes. Each script produces CSV output summarizing resource counts by type, account/subscription/project, and region.

Script versions: AWS `2.8.1` · Azure `2.8.4` · GCP `2.8.4` · OCI `2.8.0`

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Authentication](#authentication)
- [Required Permissions](#required-permissions)
- [Running the Scripts](#running-the-scripts)
- [Output Files](#output-files)
- [Resource Types Counted](#resource-types-counted)
- [AI / LLM Resources](#ai--llm-resources)
- [Troubleshooting](#troubleshooting)

---

## Overview

Each script connects to one cloud provider, iterates over every active account / subscription / project / compartment, and counts resources by type. Results are printed to stdout in real time and written to CSV files when the run completes.

**Three optional counting modes extend the default set:**

| Flag | What it adds |
|------|-------------|
| `--data` | Data Buckets, PaaS Databases, Data Warehouses |
| `--images` | Registry Container Images (ECR / ACR / GAR) |
| `--ai` | AI/LLM resources (Bedrock, Azure AI Foundry, Vertex AI) |

All three flags are off by default. They may be combined freely.

---

## Prerequisites

- Python 3.8 or later
- Cloud provider CLI tools installed and authenticated before running the scripts (see [Authentication](#authentication))
- Network access to the cloud provider control-plane APIs

---

## Setup

```bash
# Create and activate a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies for the cloud(s) you intend to scan
# (see per-cloud install commands below)
```

### AWS

```bash
pip3 install --upgrade boto3 botocore eks_token kubernetes urllib3
```

### Azure

```bash
pip3 install --upgrade \
    azure-mgmt-resourcegraph \
    azure-containerregistry \
    azure-identity \
    azure-mgmt-appcontainers \
    azure-mgmt-azurestackhci \
    azure-mgmt-cognitiveservices \
    azure-mgmt-compute \
    azure-mgmt-containerinstance \
    azure-mgmt-containerregistry \
    azure-mgmt-containerservice \
    azure-mgmt-hybridcompute \
    azure-mgmt-sql \
    azure-mgmt-storage \
    azure-mgmt-subscription \
    azure-mgmt-web \
    azure-storage-blob \
    msrestazure
```

For `--ai` mode, also install:

```bash
pip3 install --upgrade azure-ai-agents azure-ai-projects
```

### GCP

```bash
pip3 install --upgrade google-api-python-client
```

### OCI

```bash
pip3 install --upgrade oci
```

---

## Authentication

Authenticate in your shell before running any script. The scripts do not accept credentials as arguments; they rely entirely on ambient credentials from the environment.

### AWS

Configure the AWS CLI or set environment variables:

```bash
# Option 1: interactive configuration
aws configure

# Option 2: environment variables
export AWS_ACCESS_KEY_ID=<key>
export AWS_SECRET_ACCESS_KEY=<secret>
export AWS_DEFAULT_REGION=us-east-1

# Verify
aws sts get-caller-identity
```

For multi-account scans (`--all` or `--accounts`), the credentials must belong to an IAM principal that can call `sts:AssumeRole` into each member account. The default role name assumed is `OrganizationAccountAccessRole`; override with `--role-name`.

### Azure

```bash
az login
az account set --subscription <subscription-id>

# Verify
az account show
```

The script uses `azure.identity.DefaultAzureCredential`, which also accepts service principal environment variables (`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`) and managed identity when running inside Azure.

### GCP

```bash
gcloud auth application-default login

# Verify the active project
gcloud config get-value project
```

The script calls `google.auth.default()`, so any method that populates Application Default Credentials (ADC) works: `gcloud auth application-default login`, a service account key file via `GOOGLE_APPLICATION_CREDENTIALS`, or a metadata server when running on GCP.

### OCI

```bash
# Interactive setup — creates ~/.oci/config
oci setup config
```

The script reads `~/.oci/config` using the `DEFAULT` profile (`oci.config.DEFAULT_LOCATION`, `oci.config.DEFAULT_PROFILE`). When running inside OCI Cloud Shell, it automatically detects and uses the delegation token at `/etc/oci/delegation_token`.

---

## Required Permissions

The scripts make read-only API calls. Granting the broad read-only managed policies listed below is the fastest path to a working scan. The table of specific actions is provided for teams that require least-privilege custom policies.

### AWS

**Recommended managed policies:** `ReadOnlyAccess`

For a tighter custom policy, the script makes the following API calls:

| Service | boto3 client | Methods called |
|---------|-------------|----------------|
| STS | `sts` | `get_caller_identity` |
| Organizations | `organizations` | `describe_organization`, `list_accounts` |
| EC2 | `ec2` | `describe_regions`, `describe_instances` |
| Lightsail | `lightsail` | `get_regions`, `get_instances` |
| ECS | `ecs` | `list_clusters`, `list_container_instances`, `list_tasks`, `describe_tasks` |
| EKS | `eks` | `list_clusters`, `list_fargate_profiles`, `describe_cluster` |
| Lambda | `lambda` | `list_functions`, `list_versions_by_function` |
| SageMaker | `sagemaker` | `list_domains`, `list_endpoints` |
| ECR | `ecr` | `describe_repositories`, `list_images` |
| S3 | `s3` | `list_buckets` |
| DocumentDB | `docdb` | `describe_db_clusters` |
| RDS | `rds` | `describe_db_clusters`, `describe_db_instances` |
| Redshift | `redshift` | `describe_clusters` |
| DynamoDB | `dynamodb` | `list_tables` |
| Bedrock | `bedrock` | `list_custom_models` |
| Bedrock Agent | `bedrock-agent` | `list_agents` |

Minimum IAM actions for a custom policy:

```
sts:GetCallerIdentity
organizations:DescribeOrganization
organizations:ListAccounts
ec2:DescribeRegions
ec2:DescribeInstances
lightsail:GetRegions
lightsail:GetInstances
ecs:ListClusters
ecs:ListContainerInstances
ecs:ListTasks
ecs:DescribeTasks
eks:ListClusters
eks:ListFargateProfiles
eks:DescribeCluster
lambda:ListFunctions
lambda:ListVersionsByFunction
sagemaker:ListDomains
sagemaker:ListEndpoints
ecr:DescribeRepositories
ecr:ListImages
s3:ListAllMyBuckets
rds:DescribeDBClusters
rds:DescribeDBInstances
docdb:DescribeDBClusters
redshift:DescribeClusters
dynamodb:ListTables
bedrock:ListCustomModels
bedrock-agent:ListAgents
```

For multi-account scans, the scanning principal also needs:

```
sts:AssumeRole
```

on the target account roles.

### Azure

**Recommended role:** `Reader` at subscription scope

For `--ai` mode, additionally assign `Cognitive Services Reader` at subscription scope.

The script instantiates the following SDK clients and calls their list methods:

| SDK Client | Used for | Methods called |
|-----------|----------|----------------|
| `SubscriptionClient` | Subscription enumeration | `subscriptions.list`, `subscriptions.get` |
| `ComputeManagementClient` | VMs, Scale Set VMs | `virtual_machines.list_all`, `virtual_machine_scale_sets.list_all`, `virtual_machine_scale_set_vms.list`, `virtual_machines.get` |
| `ContainerServiceClient` | AKS nodes | `managed_clusters.list` |
| `ContainerInstanceManagementClient` | Container Instances | `container_groups.list` |
| `ContainerAppsAPIClient` | Container Apps | `container_apps.list_by_subscription` |
| `WebSiteManagementClient` | Web Apps / Functions | `web_apps.list`, `web_apps.list_functions`, `app_service_plans.list` |
| `HybridComputeManagementClient` | Azure Arc machines | `machines.list_by_subscription` |
| `AzureStackHCIClient` | Stack HCI clusters | `clusters.list_by_subscription` |
| `StorageManagementClient` | Storage containers | `storage_accounts.list`, `blob_containers.list` |
| `SqlManagementClient` | Azure SQL databases | `servers.list`, `databases.list_by_server` |
| `ContainerRegistryManagementClient` | ACR registry list | `registries.list` |
| `ContainerRegistryClient` | ACR image tags | `list_repository_names`, `get_repository_properties` |
| `CognitiveServicesManagementClient` | AI model deployments, AI agents | `accounts.list`, `deployments.list` |
| `AgentsClient` | AI Agents (OpenAI Assistants) | `list_agents` |
| `AIProjectClient` | AI Agents (AI Foundry) | `agents.list` |
| `ResourceGraphClient` | Optional graph mode | `resources` |

### GCP

**Recommended roles:** `roles/viewer` on each project, or `roles/resourcemanager.organizationViewer` + `roles/viewer` for `--all` scans.

The script calls these Google API services. Each service must be enabled on the target project:

| GCP Service API | API name used | Used for |
|----------------|--------------|----------|
| Service Usage API | `serviceusage` v1 | Check which APIs are enabled per project |
| Cloud Resource Manager API | `cloudresourcemanager` v1 | List / get projects |
| Compute Engine API | `compute` v1 | VM instances, regions, disk images |
| Kubernetes Engine API | `container` v1 | GKE clusters and Autopilot |
| Cloud Functions API | `cloudfunctions` v2 | Cloud Functions |
| Cloud Run API | `run` v1 | Cloud Run revisions |
| Cloud Storage API | `storage` v1 | Storage buckets |
| Cloud SQL Admin API | `sqladmin` v1 | Cloud SQL instances |
| Spanner API | `spanner` v1 | Spanner instances and databases |
| BigQuery API | `bigquery` v2 | BigQuery datasets |
| Artifact Registry API | `artifactregistry` v1 | Container images in GAR |
| Vertex AI API | `aiplatform` v1 | Vertex AI Endpoints |
| Dialogflow API | `dialogflow` v3 | Vertex AI Agents (Dialogflow CX) |

The script automatically skips any API call for a service that is not enabled in the project's service list, so no errors occur for unused services.

### OCI

**Recommended policy:** A group with `inspect` and `read` verbs on all resource families in the tenancy or target compartments.

Minimum OCI IAM policy statements:

```
Allow group <ReadGroup> to inspect compartments in tenancy
Allow group <ReadGroup> to inspect instances in tenancy
Allow group <ReadGroup> to read instances in tenancy
Allow group <ReadGroup> to inspect functions-family in tenancy
Allow group <ReadGroup> to inspect buckets in tenancy
```

The script uses these OCI SDK clients:

| OCI Client | Used for |
|-----------|----------|
| `oci.identity.IdentityClient` | List compartments, regions |
| `oci.resource_search.ResourceSearchClient` | Query instances, functions, buckets |
| `oci.core.ComputeClient` | Get image OS details |

---

## Running the Scripts

### AWS

```bash
# Scan the current account (prompts for nothing; uses ambient credentials)
python3 resource-count-aws-v2.py

# Scan a specific account ID
python3 resource-count-aws-v2.py --id 123456789012

# Scan all accounts in the AWS Organization
python3 resource-count-aws-v2.py --all

# Scan a list of accounts from a file (one 12-digit ID per line)
python3 resource-count-aws-v2.py --accounts
# Reads: accounts.txt

# Scan only the regions listed in a file (one region name per line)
python3 resource-count-aws-v2.py --regions
# Reads: regions.txt

# Use a custom cross-account role name
python3 resource-count-aws-v2.py --all --role-name MyReadOnlyRole

# GovCloud partition
python3 resource-count-aws-v2.py --gov

# China partition
python3 resource-count-aws-v2.py --china

# Enable data, image, and AI counts
python3 resource-count-aws-v2.py --data --images --ai

# Tune Lambda version counting (default 5, range 0-10)
python3 resource-count-aws-v2.py --max-lambda-versions 3

# Tune image tag counting per repository (default 5, range 1-1000)
python3 resource-count-aws-v2.py --images --max-image-tags 10

# Control parallelism
python3 resource-count-aws-v2.py --max-workers 16

# Debug mode: sequential execution, exits on first error
python3 resource-count-aws-v2.py --debug

# Verbose: prints every API response object
python3 resource-count-aws-v2.py --verbose
```

### Azure

```bash
# Scan a specific subscription (interactive prompt if --id is omitted)
python3 resource-count-azure-v2.py --id <subscription-uuid>

# Scan all subscriptions visible to the authenticated principal
python3 resource-count-azure-v2.py --all

# Scan subscriptions listed in a file (one UUID per line)
python3 resource-count-azure-v2.py --subscriptions
# Reads: subscriptions.txt

# Sovereign cloud modes (mutually exclusive)
python3 resource-count-azure-v2.py --gov
python3 resource-count-azure-v2.py --china
python3 resource-count-azure-v2.py --germany

# Enable data, image, and AI counts
python3 resource-count-azure-v2.py --data --images --ai

# Enable experimental Azure Resource Graph mode
python3 resource-count-azure-v2.py --graph

# Tune image tag counting per repository (default 5, range 1-1000)
python3 resource-count-azure-v2.py --images --max-image-tags 10

# Control parallelism
python3 resource-count-azure-v2.py --max-workers 16

# Debug and verbose modes
python3 resource-count-azure-v2.py --debug
python3 resource-count-azure-v2.py --verbose
```

### GCP

```bash
# Scan a specific project (interactive prompt if --id is omitted)
python3 resource-count-gcp-v2.py --id my-gcp-project-id

# Scan all projects accessible to the authenticated principal
python3 resource-count-gcp-v2.py --all

# Scan projects listed in a file (one project ID per line)
python3 resource-count-gcp-v2.py --projects
# Reads: projects.txt

# Exclude projects in specific folders (one folder ID per line)
python3 resource-count-gcp-v2.py --all --exclude
# Reads: excluded-folders.txt

# Enable data, image, and AI counts
python3 resource-count-gcp-v2.py --data --images --ai

# Tune image tag counting per repository (default 5, range 1-1000)
python3 resource-count-gcp-v2.py --images --max-image-tags 10

# Control parallelism
python3 resource-count-gcp-v2.py --max-workers 16

# Debug and verbose modes
python3 resource-count-gcp-v2.py --debug
python3 resource-count-gcp-v2.py --verbose
```

### OCI

```bash
# Scan all compartments in the tenancy (uses ~/.oci/config DEFAULT profile)
python3 resource-count-oci.py

# Include bucket counts
python3 resource-count-oci.py --data

# Control parallelism
python3 resource-count-oci.py --max-workers 16

# Debug and verbose modes
python3 resource-count-oci.py --debug
python3 resource-count-oci.py --verbose
```

> OCI does not support `--all`, `--id`, `--images`, or `--ai` flags. The script always scans every compartment in the tenancy derived from the active `~/.oci/config` profile.

---

## Output Files

Each script writes three files to the current working directory on completion.

### AWS

| File | Contents |
|------|----------|
| `aws-resources.csv` | Summary: `Resource Type, Resource Count` — one row per enabled resource category |
| `aws-resources-log.csv` | Detail: `Resource Type, Resource Count, Account, Region` — one row per region per account |
| `aws-errors-log.txt` | One line per API error encountered; only written if errors occurred |

### Azure

| File | Contents |
|------|----------|
| `azure-resources.csv` | Summary: `Resource Type, Resource Count` |
| `azure-resources-log.csv` | Detail: `Resource Type, Resource Count, Subscription` |
| `azure-errors-log.txt` | API errors; only written if errors occurred |

### GCP

| File | Contents |
|------|----------|
| `gcp-resources.csv` | Summary: `Resource Type, Resource Count` |
| `gcp-resources-log.csv` | Detail: `Resource Type, Resource Count, Project, Region` |
| `gcp-errors-log.txt` | API errors; only written if errors occurred |

### OCI

| File | Contents |
|------|----------|
| `oci-resources.csv` | Summary: `Resource Type, Resource Count` |
| `oci-resources-log.csv` | Detail: `Resource Type, Resource Count, Region` |
| `oci-errors-log.txt` | API errors; only written if errors occurred |

---

## Resource Types Counted

The table below maps every resource category to the underlying service and the flag required to enable it.

### AWS (`resource-count-aws-v2.py`)

| Resource Category | Underlying Services | Flag |
|------------------|--------------------|----|
| Virtual Machines | EC2 Instances, Lightsail Instances | default |
| Container Hosts | ECS Container Instances, EKS Nodes | default |
| Serverless Functions | Lambda Functions + up to N versions | default |
| Serverless Containers | ECS Fargate Tasks (containers), EKS Fargate Pods, SageMaker Domains, SageMaker Endpoints | default |
| Non-OS Disks | EBS data volumes attached to EC2 and Lightsail | default |
| Data Buckets | S3 Buckets (capped at 10,000) | `--data` |
| PaaS Databases | DocumentDB Clusters, RDS Aurora Clusters, RDS Instances (MariaDB/MySQL/Oracle/PostgreSQL/MSSQL), Redshift Clusters | `--data` |
| Data Warehouses | DynamoDB Tables (capped at 10,000) | `--data` |
| Registry Container Images | ECR images (up to `--max-image-tags` tags per repository) | `--images` |
| Bedrock Custom Models | Custom fine-tuned Bedrock models | `--ai` |
| Bedrock Agents | Bedrock Agent definitions | `--ai` |

### Azure (`resource-count-azure-v2.py`)

| Resource Category | Underlying Services | Flag |
|------------------|--------------------|----|
| Virtual Machines | Compute VMs (excluding Databricks), Scale Set VMs (excluding Databricks) | default |
| Container Hosts | AKS Managed Cluster node counts | default |
| Serverless Functions | Web Apps (all kinds), child Functions within Function Apps | default |
| Serverless Containers | Azure Container Instances (groups), Azure Container Apps | default |
| Asset Metadata | Azure Arc Machines, Azure Stack HCI Clusters | default |
| Non-OS Disks | Data disks on Compute VMs and Scale Set VMs | default |
| Data Buckets | Blob Storage Containers (per storage account, excluding Databricks accounts) | `--data` |
| PaaS Databases | Azure SQL Databases (excluding `master`) | `--data` |
| Registry Container Images | ACR images (up to `--max-image-tags` tags per repository) | `--images` |
| AI Model Deployments | Azure OpenAI and AIServices deployments via Cognitive Services | `--ai` |
| AI Agents | Azure AI Foundry agents and OpenAI Assistants | `--ai` |

### GCP (`resource-count-gcp-v2.py`)

| Resource Category | Underlying Services | Flag |
|------------------|--------------------|----|
| Virtual Machines | Compute Engine Instances (excluding Databricks, excluding GKE nodes) | default |
| Container Hosts | GKE Standard nodes (identified by `goog-gke-node` label) | default |
| Serverless Functions | Cloud Functions (v2 API, all locations) | default |
| Serverless Containers | Cloud Run active revisions, GKE Autopilot pod capacity | default |
| Non-OS Disks | Non-boot persistent disks on Compute Instances | default |
| Data Buckets | Cloud Storage Buckets (capped at 10,000) | default* |
| PaaS Databases | Cloud SQL Instances, Spanner Databases | default* |
| Data Warehouses | BigQuery Datasets | default* |
| Registry Container Images | Artifact Registry Docker images (up to `--max-image-tags` tags per image) | `--images` |
| Vertex AI Endpoints | Vertex AI Endpoints (all locations) | `--ai` |
| Vertex AI Agents | Dialogflow CX Agents (all locations) | `--ai` |

> *GCP enables Data Buckets, PaaS Databases, and Data Warehouses by default (not gated behind `--data`). The `--data` flag has no effect on GCP currently; those resources are always counted.

### OCI (`resource-count-oci.py`)

| Resource Category | Underlying Services | Flag |
|------------------|--------------------|----|
| Virtual Machines | Compute Instances (non-terminated, non-terminating, across all compartments) | default |
| Container Hosts | OKE-tagged Compute Instances (identified by `Oracle-Tags.CreatedBy = oke`) | default |
| Serverless Functions | OCI Functions (`functionsfunction` resources) | default |
| Data Buckets | OCI Object Storage Buckets | `--data` |

> OCI does not currently support `--images` or `--ai` modes.

---

## AI / LLM Resources

The `--ai` flag activates counting of AI/LLM resources on AWS, Azure, and GCP. This section details exactly what is counted and which API endpoint or service is queried.

### AWS — `--ai`

| Resource | boto3 client | Method | Notes |
|----------|-------------|--------|-------|
| Bedrock Custom Models | `bedrock` | `list_custom_models` | Counts fine-tuned/custom foundation models per region. Silently skips regions where Bedrock is not available (endpoint resolution errors are suppressed). |
| Bedrock Agents | `bedrock-agent` | `list_agents` | Counts Bedrock Agent definitions per region. Same endpoint-not-available suppression applies. |

Both resources are scanned in every active region. Regions where Bedrock is not yet available produce no errors.

Required permissions beyond the default set:

```
bedrock:ListCustomModels
bedrock-agent:ListAgents
```

### Azure — `--ai`

| Resource | SDK Client | Method | Notes |
|----------|-----------|--------|-------|
| AI Model Deployments | `CognitiveServicesManagementClient` | `accounts.list` + `deployments.list` | Filters to accounts with `kind` of `OpenAI` or `AIServices` only. Counts every deployment within those accounts. |
| AI Agents | `CognitiveServicesManagementClient` + `AgentsClient` + `AIProjectClient` | `accounts.list` → `list_agents` / `agents.list` | For each OpenAI/AIServices account that exposes an `AI Foundry API` endpoint, counts both OpenAI Assistants (via `AgentsClient`) and AI Foundry template agents (via `AIProjectClient`). Errors per project are logged as verbose output and do not abort the run. |

Required additional packages for `--ai`:

```bash
pip3 install --upgrade azure-ai-agents azure-ai-projects
```

Required Azure role beyond `Reader`: `Cognitive Services Reader` at subscription scope.

### GCP — `--ai`

| Resource | Google API | Service string | Method | Notes |
|----------|-----------|---------------|--------|-------|
| Vertex AI Endpoints | `aiplatform` v1 | `aiplatform.googleapis.com` | `projects.locations.endpoints.list` with `locations/-` (all locations) | Only runs if `aiplatform.googleapis.com` is enabled in the project's service list. |
| Vertex AI Agents | `dialogflow` v3 | `dialogflow.googleapis.com` | `projects.locations.agents.list` with `locations/-` (all locations) | Counts Dialogflow CX agents. Only runs if `dialogflow.googleapis.com` is enabled. |

Required GCP roles beyond `roles/viewer`: none — `roles/viewer` includes read access to both APIs.

---

## Troubleshooting

**Script exits with "Missing required ... packages"**
Run the pip install command printed in the error message, then retry.

**`aws sts get-caller-identity` fails**
Your AWS credentials are not configured. Run `aws configure` or export `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION`.

**Azure script prompts "Enter the Azure Subscription ID to scan"**
Neither `--id`, `--all`, nor `--subscriptions` was provided. Pass `--id <uuid>` to avoid the prompt.

**GCP script prompts "Enter the GCP Project ID to scan"**
Neither `--id`, `--all`, nor `--projects` was provided. Pass `--id <project-id>` to avoid the prompt.

**Errors appear in `*-errors-log.txt` but the run completes**
Parallel mode continues past individual API failures. Review the log file for access-denied or quota errors, then fix permissions or reduce `--max-workers`. Rerun with `--debug` to convert the first error into a hard stop with a full traceback.

**Bedrock / Vertex AI returns zero counts despite having resources**
Confirm the service is enabled in that region/project and that the IAM principal has the required read permissions. For Bedrock, the script silently skips regions where the endpoint does not resolve; use `--verbose` to see which regions are skipped.

**OCI "Error reading OCI configuration"**
Run `oci setup config` to create `~/.oci/config`, or confirm the file exists and contains a `[DEFAULT]` profile with valid `tenancy`, `user`, `fingerprint`, and `key_file` entries.

**Counts seem too high for Lambda**
The script counts each function plus up to `--max-lambda-versions` published versions per function. The default is 5. Set `--max-lambda-versions 0` to count only the `$LATEST` function and suppress version counting.
