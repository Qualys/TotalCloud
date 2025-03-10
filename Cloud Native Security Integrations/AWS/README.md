# Qualys TotalCloud Integration with AWS GuardDuty

## Overview
This AWS CloudFormation template deploys an EventBridge-based integration for **Qualys TotalCloud Integration with AWS GuardDuty**. The deployment includes IAM roles, policies, API Destinations, and EventBridge rules to automate the forwarding of AWS GuardDuty findings to Qualys TotalCloud.

## Features
- 🚀 **IAM Roles and Policies**: Grants necessary permissions to invoke API destinations and manage event rules.
- 🔄 **EventBridge Rules**: Triggers assessments when GuardDuty detects findings.
- 🌍 **Cross-Region Deployment**: Uses AWS StackSets to deploy the EventBridge rule across multiple regions.
- 🔐 **API Destinations**: Securely connects to Qualys TotalCloud API for findings forwarding.

## 📌 Resources Deployed

### **IAM Roles & Policies**
- **`RoleForAPIDestination`** - IAM Role to provide access to API Destination.
- **`PolicyAPIBased`** - IAM Policy allowing invocation of API Destinations.
- **`StackSetAdministrationRole`** - IAM Role for CloudFormation StackSet administration.
- **`StackSetExecutionRole`** - IAM Role with permissions for cross-region stack execution.

### **EventBridge Configuration**
- **`APIConnection`** - Configures authentication for the API Destination.
- **`APIDestinationApiDestinationGuardduty`** - Defines the API Destination for Qualys TotalCloud GuardDuty integration.
- **`EventRuleGuardDuty`** - Listens for AWS GuardDuty findings and triggers Qualys TotalCloud processing.
- **`RegionStackSet`** - Deploys EventBridge rules across multiple AWS regions.

## ⚙️ Parameters
| Parameter | Description |
|-----------|-------------|
| **`SubscriptionToken`** | Token required for authentication with Qualys TotalCloud API. |
| **`APIGatewayURL`** | Qualys TotalCloud API Gateway URL. |
| **`Regions`** | List of AWS regions where EventBridge rules will be deployed. |

## 🚀 Deployment Instructions
### **Using the AWS Management Console**
1. Navigate to the **AWS CloudFormation Console**.
2. Click on **Create Stack** → **With new resources**.
3. Upload the **CloudFormation template**.
4. Provide the required **parameters**.
5. Click **Next** and configure stack options if needed.
6. Click **Create Stack** and wait for deployment to complete.

### **Using AWS CLI**
Run the following command:
```sh
aws cloudformation deploy --template-file template.yml --stack-name qualys-findings-stack --capabilities CAPABILITY_NAMED_IAM
```

### **Using AWS CDK**
If using **AWS CDK**, deploy using:
```sh
cdk deploy
```

## 🤝 Contributors
- **Yash Jhunjhunwala (Lead SME, Cloud Secuirty)** - Initial implementation

## 📖 Additional Information
Refer to the [Qualys Documentation](https://docs.qualys.com/en/conn/latest/#t=scans%2Fsnapshot-based_scan.htm) for generating the **SubscriptionToken** and other necessary setup details.

---
*Happy Deploying! 🚀*

