# OCI Connectors

Terraform configuration for connecting an OCI tenancy to Qualys TotalCloud.

[`Setup/Terraform/`](Setup/Terraform/) creates the OCI policies and dynamic group that grant Qualys read access to your tenancy. Deploy it once and use the outputs to configure the connector in the Qualys portal.

See the [README inside `Setup/Terraform/`](Setup/Terraform/README.md) for required OCI permissions and deployment steps.
