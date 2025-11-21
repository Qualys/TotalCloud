# Vertex AI Model Count Script
============================

This script checks all Google Cloud projects that the user has access to and counts
how many Vertex AI models exist in each region. It uses curl to call the Vertex AI
REST API and writes the results into a CSV file.

The script is read-only and does not create or modify any resources.

----------------------------------------------------------------------
## Requirements
----------------------------------------------------------------------

The following tools must be available in the environment:

- curl
- jq
- gcloud CLI

Most Cloud Shell environments already provide these.

Make sure you are logged in:

    gcloud auth login
    gcloud auth application-default login

----------------------------------------------------------------------
## Required IAM Permissions
----------------------------------------------------------------------

To run the script successfully, the user or service account needs:

1. Permission to list Google Cloud projects:
   - roles/resourcemanager.projectViewer
   OR
   - roles/viewer
   OR
   - direct viewer access on individual projects

2. Permission to read Vertex AI model metadata in each project:
   - roles/aiplatform.viewer
   OR
   - roles/aiplatform.admin
   OR
   - a custom role including:
        aiplatform.models.list
        aiplatform.models.get

3. Permission to obtain an access token:
   - Normally granted by default to any logged-in user
   - Service accounts may require: roles/iam.serviceAccountTokenCreator

----------------------------------------------------------------------
## How to Run the Script
----------------------------------------------------------------------

1. Upload or copy the script to your environment (e.g., Cloud Shell).

2. Make it executable:

       chmod +x gcp-vertex-model-count.sh

3. Run it:

       ./gcp-vertex-model-count.sh

4. After completion, the output file will be created:

       vertex_model_counts.csv

----------------------------------------------------------------------
## Output
----------------------------------------------------------------------

The script generates a CSV file with three columns:

    project_id,region,count

Example:

    project-1,us-central1,3
    project-1,asia-east1,0
    project-2,us-central1,1

This file can be opened in Excel, Google Sheets, or any CSV viewer.

----------------------------------------------------------------------
## Notes
----------------------------------------------------------------------

- Many regions do not support Vertex AI and will always show 0 models.
- Scan time depends on the number of projects and regions.
- All operations are read-only; no changes are made to your environment.

----------------------------------------------------------------------
## Maintainer
----------------------------------------------------------------------
Yash Jhunjhunwala (Lead Solutions Architect, Cloud Security)
