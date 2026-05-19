# Create AWS TotaCloud Individual Connector via Terraform

This repository contains a Terraform script to set up a Qualys TotaCloud AWS Connector. The script creates an IAM role with the necessary permissions and configures the connector using Qualys API.

## Disclaimer

THIS SCRIPT IS PROVIDED TO YOU "AS IS." TO THE EXTENT PERMITTED BY LAW, QUALYS HEREBY DISCLAIMS ALL WARRANTIES AND LIABILITY FOR THE PROVISION OR USE OF THIS SCRIPT. IN NO EVENT SHALL THESE SCRIPTS BE DEEMED TO BE CLOUD SERVICES AS PROVIDED BY QUALYS.

## Prerequisites

- Terraform installed on your local machine.
- AWS account with permissions to create IAM roles and policies.
- Qualys Platform credentials.

## Usage

### Step 1: Clone the repository

```sh
git clone https://github.com/Qualys/TotalCloud.git
cd Connectors/Connector Terraform Templates/AWS/
```

### Step 2: Initialize Terraform
```sh
terraform init
```

### Step 3: Apply the Terraform Configuration
Run the following command and provide the required inputs when prompted:
```sh
terraform apply
```

## Input Parameters
`username`: Qualys Platform Username (sensitive).
`password`: Qualys Platform Password (sensitive).
`externalId`: ExternalId for the assume role (sensitive).

You will be prompted to enter these values during the execution of the terraform apply command.
```sh
var.username
  Enter the value for the username: [your Qualys Platform Username]

var.password
  Enter the value for the password: [your Qualys Platform Password]

var.externalId
  Enter the value for the externalId: [your ExternalId]
```
## Outputs
`ROLE_ARN`: The ARN of the created IAM role.
`CLOUDVIEW-OUTPUT`: The output from the Qualys CloudView API call.
`CLOUDVIEW-EXIT-STATUS`: The exit status of the Qualys CloudView API call.

## Variables
The following variables can be configured in the variables.tf file or passed as inputs:

`connector_type`: Type of connector. Default is CSA.
`username`: Qualys Platform Username.
`password`: Qualys Platform Password.
`externalId`: ExternalId for the assume role.
`baseurl`: Qualys Platform API server URL. Default is https://qualysapi.qg1.apps.qualys.ca.

## Exapmle
```sh
terraform apply -var="username=your-username" -var="password=your-password" -var="externalId=your-externalId"
```

## Author
Yash Jhunjhunwala
