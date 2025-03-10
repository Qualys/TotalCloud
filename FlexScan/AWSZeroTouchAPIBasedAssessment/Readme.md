# Qualys Zero-Touch API-Based Assessment

## Overview
This AWS CloudFormation template deploys an EventBridge-based integration for **Qualys AWS Zero-Touch API-Based Assessment**. The deployment includes IAM roles, policies, API Destinations, and EventBridge rules to automate the scanning of EC2 instances upon launch.

## Features
- 🚀 **IAM Roles and Policies**: Grants necessary permissions to invoke API destinations and manage event rules.
- 🔄 **EventBridge Rules**: Triggers assessments when EC2 instances enter the "running" state.
- 🌍 **Cross-Region Deployment**: Uses AWS StackSets to deploy the EventBridge rule across multiple regions.
- 🔐 **API Destinations**: Securely connects to Qualys API for assessments.

## 📌 Resources Deployed

### **IAM Roles & Policies**
- **`RoleForAPIDestination`** - IAM Role to provide access to API Destination.
- **`PolicyAPIBased`** - IAM Policy allowing invocation of API Destinations.
- **`StackSetAdministrationRole`** - IAM Role for CloudFormation StackSet administration.
- **`StackSetExecutionRole`** - IAM Role with permissions for cross-region stack execution.

### **EventBridge Configuration**
- **`APIConnection`** - Configures authentication for the API Destination.
- **`APIDestinationApiDestination`** - Defines the API Destination for Qualys.
- **`EventRule`** - Listens for EC2 instance state changes and triggers Qualys assessment.
- **`RegionStackSet`** - Deploys EventBridge rules across multiple AWS regions.

## ⚙️ Parameters
| Parameter | Description |
|-----------|-------------|
| **`SubscriptionToken`** | Token required for authentication with Qualys API. |
| **`APIGatewayURL`** | Qualys API Gateway URL. |
| **`Regions`** | List of AWS regions where EventBridge rules will be deployed. |

## 🚀 Deployment Instructions
1. **Ensure you have the required permissions** to create IAM roles, policies, EventBridge rules, and CloudFormation StackSets.
2. **Update the parameters** with appropriate values.
3. **Deploy the CloudFormation stack** using:
   - **AWS Management Console**
   - **AWS CLI** (`aws cloudformation deploy --template-file template.yml --stack-name qualys-ssm-stack`)
   - **Infrastructure-as-Code (IaC) tools** like AWS CDK.

## 🤝 Contributors
- **Yash Jhunjhunwala (Lead SME, Cloud Secuirty)**

## 📖 Additional Information
Refer to the [Qualys Documentation](https://docs.qualys.com/en/conn/latest/#t=scans%2Fsnapshot-based_scan.htm) for generating the **SubscriptionToken** and other necessary setup details.

---
*Happy Deploying! 🚀*
