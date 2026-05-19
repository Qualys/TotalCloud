##################################
# THIS SCRIPT IS PROVIDED TO YOU "AS IS." TO THE EXTENT PERMITTED BY LAW, QUALYS HEREBY DISCLAIMS ALL WARRANTIES AND LIABILITY 
# FOR THE PROVISION OR USE OF THIS SCRIPT. IN NO EVENT SHALL THESE SCRIPTS BE DEEMED TO BE CLOUD SERVICES AS PROVIDED BY QUALYS
#
# Author: Yash Jhunjhunwala
#
# INPUT THE FOLLOWING PARAMETERS
#
# username: Qualys Platform Username
# password: Qualys Platform Password
# baseurl: Qualys Platform API server for URL
##################################

variable "connector_type" {
  type        = string
  description = "If set to CSA creates CSMP Connector ; If set to AI creates AssetView Connector ; Default is CSA"
  default     = "CSA"
}

variable "username" {
  type        = string
  description = "Qualys Platform Username."
  sensitive   = true
}

variable "password" {
  type        = string
  description = "Qualys Platform Password."
  sensitive   = true
}

variable "externalId" {
  type        = string
  description = "ExternalId for the assume role."
}

variable "baseurl" {
  type        = string
  description = "Qualys Platform API server, You can find Platform Wise URL here :- https://www.qualys.com/platform-identification/"
  default     = "https://qualysapi.qg1.apps.qualys.ca"
}

provider "aws" {
  region = "us-east-1"
}

resource "aws_iam_role" "QualysReadOnlyRole" {
  name = "QualysCSPMReadOnlyRole"

  assume_role_policy = jsonencode({
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": "sts:AssumeRole",
        "Principal": {
          "AWS": "arn:aws:iam::805950163170:root"
        },
        "Condition": {
          "StringEquals": {
            "sts:ExternalId": var.externalId
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "QualysCSPMReadOnlyPolicy" {
  name   = "QualysCSPMReadOnlyPolicy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        "Sid": "QualysCustomPolicyPermissions",
        "Effect": "Allow",
        "Action": [
          "states:DescribeStateMachine", "elasticfilesystem:DescribeFileSystemPolicy", "qldb:ListLedgers", "qldb:DescribeLedger", "kafka:ListClusters", "codebuild:BatchGetProjects", "wafv2:GetWebACLForResource", "backup:ListBackupVaults", "backup:DescribeBackupVault", "ec2:GetEbsEncryptionByDefault", "ec2:GetEbsDefaultKmsKeyId", "guardduty:ListDetectors", "guardduty:GetDetector", "glue:GetDataCatalogEncryptionSettings", "elasticmapreduce:GetBlockPublicAccessConfiguration", "lambda:GetFunctionConcurrency", "ds:ListLogSubscriptions", "ssm:getdocument", "ssm:getservicesetting", "states:GetExecutionHistory", "eks:ListFargateProfiles", "eks:DescribeFargateProfile"
        ],
        "Resource": "*"
      },
      {
        "Sid": "QualysAPIGatewayGetPermissions",
        "Effect": "Allow",
        "Action": "apigateway:GET",
        "Resource": "arn:aws:apigateway:*::/restapis/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "system_defined_policy_attach" {
  role       = aws_iam_role.QualysReadOnlyRole.name
  policy_arn = "arn:aws:iam::aws:policy/SecurityAudit"
}

resource "aws_iam_role_policy_attachment" "custom_policy_attach" {
  role       = aws_iam_role.QualysReadOnlyRole.name
  policy_arn = aws_iam_policy.QualysCSPMReadOnlyPolicy.arn
}

resource "local_file" "authentication_key" {
  content = jsonencode({
    "ServiceRequest": {
      "data": {
        "AwsAssetDataConnector": {
          "name": "AWS-connector-${substr(aws_iam_role.QualysReadOnlyRole.arn, 13, 12)}",
          "arn": aws_iam_role.QualysReadOnlyRole.arn,
          "externalId": var.externalId,
          "allRegions": "true",
          "runFrequency": "240",
          "activation": {
            "set": {
              "ActivationModule": [
                "VM",
                "PC"
              ]
            }
          },
          "connectorAppInfos": {
            "set": {
              "ConnectorAppInfoQList": [
                {
                  "set": {
                    "ConnectorAppInfo": {
                      "name": var.connector_type,
                      "identifier": aws_iam_role.QualysReadOnlyRole.arn
                    }
                  }
                }
              ]
            }
          }
        }
      }
    }
  })
  filename   = "${path.module}/file.json"
  depends_on = [
    aws_iam_role_policy_attachment.system_defined_policy_attach,
    aws_iam_role_policy_attachment.custom_policy_attach
  ]
}

module "QualysCloudViewAssetViewConnector" {
  source  = "matti/resource/shell"
  command = <<EOT
    curl -u '${var.username}:${var.password}' \
    --header 'Content-Type: application/json' \
    --header 'Accept: application/xml' \
    -X POST \
    --data-binary @- ${var.baseurl}/qps/rest/3.0/create/am/awsassetdataconnector < file.json
  EOT
  depends_on = [
    aws_iam_role_policy_attachment.system_defined_policy_attach,
    aws_iam_role_policy_attachment.custom_policy_attach
  ]
}

output "ROLE_ARN" {
  value = aws_iam_role.QualysReadOnlyRole.arn
}

output "CLOUDVIEW-OUTPUT" {
  value = module.QualysCloudViewAssetViewConnector.stdout
}

output "CLOUDVIEW-EXIT-STATUS" {
  value = module.QualysCloudViewAssetViewConnector.exitstatus
}
