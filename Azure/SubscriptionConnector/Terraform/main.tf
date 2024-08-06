terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.0.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = ">= 2.0.0"
    }
    local = {
      source  = "hashicorp/local"
      version = ">= 2.0.0"
    }
  }
}

provider "azurerm" {
  features {}
}

provider "azuread" {}

# Data sources to fetch current subscription and tenant details
data "azurerm_subscription" "primary" {}

data "azurerm_client_config" "example" {}

# Create Azure AD Application
resource "azuread_application" "example" {
  display_name = var.application_display_name
  owners       = [data.azurerm_client_config.example.object_id]
}

# Create Service Principal for the application
resource "azuread_service_principal" "example" {
  application_id = azuread_application.example.client_id
}

# Create a secret key for the Service Principal
resource "azuread_application_password" "example" {
  application_object_id = azuread_application.example.id
  display_name          = "example-app-secret"
  end_date_relative     = var.secret_key_expiry
}

# Assign Reader role to the Service Principal on the subscription
resource "azurerm_role_assignment" "example" {
  scope                = data.azurerm_subscription.primary.id
  role_definition_name = "Reader"
  principal_id         = azuread_service_principal.example.id
}

# Write the secret key to a local file
resource "local_file" "secret_key" {
  content  = azuread_application_password.example.value
  filename = "${path.module}/${var.secret_key_filename}"
}
