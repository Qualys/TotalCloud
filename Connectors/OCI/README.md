# OCI Connectors

Terraform configuration for connecting an OCI tenancy to Qualys TotalCloud.

[`Terraform/`](Terraform/) creates the OCI IAM user, group, policy, and API key that grant Qualys read access to your tenancy. Deploy it once and use the outputs to configure the connector in the Qualys portal.

See the [README inside `Terraform/`](Terraform/README.md) for required OCI permissions and deployment steps.

## Author
Yash Jhunjhunwala, Lead SME Cloud Security Solutions
