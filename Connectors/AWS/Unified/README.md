# Qualys CSPM and Asset Inventory AWS Unified Template

This AWS CloudFormation template automates the setup of IAM roles and policies for Qualys Cloud Security Posture Management (CSPM) or Asset Inventory in an AWS account or across an AWS Organizational Unit (OU). It supports AWS Commercial, GovCloud, and China regions, with optional StackSet deployment for multi-account environments.

## Overview

The template performs the following:
- Creates an IAM role and custom policy in the root account for Qualys to assume, granting read-only access for CSPM or Asset Inventory.
- Optionally deploys a StackSet to replicate the IAM role and policy across accounts in a specified OU.
- Supports AWS partitions: Commercial (`aws`), GovCloud (`aws-us-gov`), and China (`aws-cn`).
- Customizes permissions based on the Qualys service type (CSPM or Asset Inventory).

## Prerequisites

- **AWS Account**: An AWS account with permissions to create IAM roles, policies, and CloudFormation StackSets (`CAPABILITY_NAMED_IAM`).
- **AWS Organizations**: Required for StackSet deployment across an OU. The stack must be deployed in the management account.
- **Qualys Account Details**: Obtain the Qualys AWS account ID and External ID from Qualys documentation or support.
- **AWS CLI or Console**: For deploying the template and managing StackSets.

## Deployment Instructions

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Prepare Parameters**:
   Create a JSON file (e.g., `parameters.json`) with the required parameters (see [Parameters](#parameters) below).

   Example:
   ```json
   {
     "QualysCSPMAccount": "123456789012",
     "ExternalId": "QualysExternalId123",
     "QualysCSPMRoleName": "qualys-cspm-read-only",
     "StackSetNamePrefix": "qualys-cspm",
     "OuId": "ou-xxxx-xxxxxxxx",
     "CloudType": "Commercial",
     "QualysServiceType": "CSPM"
   }
   ```

3. **Deploy the Stack**:
   - **Single Account**:
     ```bash
     aws cloudformation create-stack \
       --stack-name QualysIntegration \
       --template-body file://template.yaml \
       --parameters file://parameters.json \
       --capabilities CAPABILITY_NAMED_IAM \
       --region us-east-1
     ```
   - **OU Deployment**:
     Ensure `OuId` is set, and deploy in the management account. The StackSet will propagate to all accounts in the OU.

4. **Verify Deployment**:
   - Check the stack status in the AWS CloudFormation console.
   - For OU deployments, monitor StackSet instances in the console to confirm deployment across accounts.
   - Use the output `RoleARN` to configure the Qualys AWS Connector in the Qualys portal.

5. **Test Role Assumption**:
   - Validate that Qualys can assume the role using the provided `ExternalId` and `RoleARN`.

## Parameters

| Parameter              | Description                                                                 | Type   | Default                     | Constraints                                                                 |
|------------------------|-----------------------------------------------------------------------------|--------|-----------------------------|-----------------------------------------------------------------------------|
| `QualysCSPMAccount`    | Qualys AWS account ID (12 digits)                                           | String | None                        | Must be a valid 12-digit AWS account ID                                     |
| `ExternalId`           | External ID for secure role assumption                                      | String | None                        | 2–1224 characters                                                          |
| `QualysCSPMRoleName`   | Name of the IAM role for Qualys                                            | String | `qualys-cspm-read-only`     | Customizable role name                                                     |
| `StackSetNamePrefix`   | Prefix for StackSet name (used if `OuId` is provided)                      | String | `qualys-cspm`               | Appended with stack name for uniqueness                                     |
| `OuId`                 | AWS OU ID (e.g., `ou-xxxx-xxxxxxxx` or `r-xxxx` for root OU)               | String | `''` (empty for single account) | Valid OU ID or empty for single-account deployment                         |
| `CloudType`            | AWS environment type                                                       | String | `Commercial`                | `Commercial`, `GovCloud`, or `China`                                       |
| `QualysServiceType`    | Qualys service type                                                        | String | `CSPM`                      | `CSPM` or `AssetInventory`                                                 |

## Outputs

| Output         | Description                                                                 |
|----------------|-----------------------------------------------------------------------------|
| `RoleARN`      | ARN of the IAM role created for Qualys in the root account                   |
| `PolicyArn`    | ARN of the custom policy created for Qualys in the root account              |
| `RoleArn` (StackSet) | ARN of the IAM role created in child accounts (from StackSet template) |
| `PolicyArn` (StackSet) | ARN of the custom policy created in child accounts (from StackSet template) |

## Notes

- **Single Account vs. OU Deployment**:
  - Set `OuId` to an empty string (`''`) for single-account deployment.
  - Provide a valid OU ID for multi-account deployment via StackSet.
- **Region Selection**:
  - The template deploys to `us-east-1` (Commercial), `us-gov-west-1` (GovCloud), or `cn-north-1` (China) based on `CloudType`.
  - For multi-region deployments, consider modifying the StackSet to include additional regions.
- **Security**:
  - The `ExternalId` enhances security for cross-account role assumption. Ensure it matches the value provided by Qualys.
  - The custom policy grants read-only permissions. Review permissions to ensure compliance with your organization’s least privilege policies.
- **StackSet Considerations**:
  - Deploy the stack in the AWS Organizations management account for OU deployments.
  - Monitor StackSet deployment status to handle any failures (20% failure tolerance is configured).
- **Cleanup**:
  - To delete the stack, use:
    ```bash
    aws cloudformation delete-stack --stack-name QualysIntegration --region us-east-1
    ```
  - For StackSets, delete instances first, then the StackSet:
    ```bash
    aws cloudformation delete-stack-instances --stack-set-name <stack-set-name> --regions us-east-1 --accounts <account-ids>
    aws cloudformation delete-stack-set --stack-set-name <stack-set-name>
    ```

## Troubleshooting

- **Invalid Account ID**: Ensure `QualysCSPMAccount` is a valid 12-digit AWS account ID provided by Qualys.
- **Role Assumption Issues**: Verify the `ExternalId` and `RoleARN` match Qualys’s configuration.
- **StackSet Failures**: Check the CloudFormation console for error details. Ensure the management account has permissions to deploy StackSets.
- **Permission Issues**: Confirm the deploying user has `CAPABILITY_NAMED_IAM` permissions.

## Author
Yash Jhunjhunwala (Lead Solutions Architect, Cloud Security)
