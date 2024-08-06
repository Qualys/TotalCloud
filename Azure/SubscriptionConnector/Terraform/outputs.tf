output "subscription_id" {
  value = data.azurerm_subscription.primary.id
}

output "tenant_id" {
  value = data.azurerm_client_config.example.tenant_id
}

output "app_id" {
  value = azuread_application.example.client_id
}

output "secret_key_file" {
  value = local_file.secret_key.filename
}
