# Azure AD Application Setup with Terraform

This Terraform configuration sets up an Azure AD Application, creates a Service Principal, generates a secret key, and assigns the Reader role to the Service Principal for a specified Azure subscription. The secret key is stored in a local file for further use.

## Prerequisites

- [Terraform](https://www.terraform.io/downloads.html) (v1.0.0 or later)
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) (optional, for authentication)
- Access to an Azure Subscription with sufficient permissions to create resources

## Files

- `variables.tf`: Contains variable definitions for configurable values.
- `main.tf`: Contains the Terraform configuration for resources and data sources.
- `outputs.tf`: Contains the output definitions for the Terraform configuration.

## Setup

1. **Clone the Repository**

    ```bash
    git clone https://github.com/your-username/your-repository.git
    cd your-repository
    ```

2. **Configure Your Azure Provider**

   Ensure you are authenticated with Azure CLI or provide credentials in your `~/.azure/credentials` file.

3. **Initialize Terraform**

    Initialize the Terraform configuration. This will download the required providers.

    ```bash
    terraform init
    ```

4. **Review the Plan**

    Generate and review an execution plan to ensure the changes meet your expectations.

    ```bash
    terraform plan
    ```

5. **Apply the Configuration**

    Apply the configuration to create the resources.

    ```bash
    terraform apply
    ```

    Confirm the action when prompted.

## Outputs

After running `terraform apply`, the following outputs will be displayed:

- `subscription_id`: The ID of the Azure subscription.
- `tenant_id`: The ID of the Azure tenant.
- `app_id`: The client ID of the Azure AD Application.
- `secret_key_file`: Path to the file containing the secret key.

## Handling Sensitive Data

- The secret key is stored in a local file `secret_key.txt` specified by the `secret_key_filename` variable. Ensure this file is handled securely and not exposed in version control systems.

## Best Practices

- **Variables**: Configurable values are defined in `variables.tf` for easy management.
- **Code Organization**: Terraform configuration is split into `main.tf`, `variables.tf`, and `outputs.tf` for clarity.
- **Sensitive Data**: Ensure sensitive data is managed securely, even though Terraform cannot mark file contents as sensitive.

## Troubleshooting

- **Deprecation Warnings**: Update deprecated attributes according to the latest provider documentation.
- **Unsupported Arguments**: Verify the supported arguments for resources in the provider documentation.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Feel free to open issues and pull requests for improvements and bug fixes. Contributions are welcome!

