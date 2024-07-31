# Cloud-Native Integrations with AWS Services

This repository contains Terraform configurations to integrate multiple AWS services like GuardDuty and Macie with Qualys. The provided Terraform files set up roles, policies, API destinations, EventBridge rules, and CloudFormation StackSets to facilitate these integrations.

## Table of Contents

- [Usage](#usage)
- [Resources](#resources)
  - [RoleForAPIDestination](#roleforapidestination)
  - [PolicyAPIBased](#policyapibased)
  - [StackSetAdministrationRole](#stacksetadministrationrole)
  - [StackSetExecutionRole](#stacksetexecutionrole)
  - [APIConnection](#apiconnection)
  - [APIDestinationApiDestinationGuardduty](#apidestinationapidestinationguardduty)
  - [EventRuleGuardDuty](#eventruleguardduty)
  - [RegionStackSet](#regionstackset)
- [Parameters](#parameters)

## Usage

1. Clone the repository:
    ```bash
    git clone https://github.com/Qualys/TotalCloud.git
    cd Cloud Native Security Integrations/AWS/
    ```

2. Initialize Terraform:
    ```bash
    terraform init
    ```

3. Review the `variables.tf` file to ensure that all necessary variables are correctly set.

4. Apply the Terraform configuration:
    ```bash
    terraform apply
    ```

5. Follow any additional setup instructions displayed after the Terraform run completes.

## Resources

### RoleForAPIDestination

This IAM role allows EventBridge to assume and access API destinations.

### PolicyAPIBased

This IAM policy allows EventBridge to invoke API destinations and put events.

### StackSetAdministrationRole

This IAM role is used for administrating CloudFormation StackSets.

### StackSetExecutionRole

This IAM role is used for executing CloudFormation StackSets.

### APIConnection

This resource defines a connection for AWS Findings to Qualys.

### APIDestinationApiDestinationGuardduty

This resource sets up an API destination for AWS GuardDuty Findings.

### EventRuleGuardDuty

This EventBridge rule triggers on GuardDuty findings and sends events to Qualys.

### RegionStackSet

This CloudFormation StackSet deploys EventBridge across multiple regions.

## Parameters

- `SubscriptionToken` - The subscription token for Qualys. Follow the steps mentioned in [UserGuide](https://docs.qualys.com/en/conn/latest/#t=scans%2Fsnapshot-based_scan.htm) to generate this token.
- `APIGatewayURL` - The Qualys API Gateway URL. Find the Gateway URL at [Qualys Platform Identification](https://www.qualys.com/platform-identification/).
- `Regions` - List of AWS regions for deploying EventBridge. Default is `us-east-1`.

For detailed information on each resource, please refer to the AWS CloudFormation documentation and the Terraform AWS provider documentation.

## Author
Yash Jhunjhunwala (Lead SME, Cloud Security)

