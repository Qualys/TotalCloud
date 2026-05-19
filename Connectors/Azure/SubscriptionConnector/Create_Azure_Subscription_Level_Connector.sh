#!/bin/bash

# Qualys API endpoint for creating AWS Connector. Ref:- https://www.qualys.com/platform-identification/
API_ENDPOINT="<Qualys_API_Server_URL>/qps/rest/3.0/create/am/azureassetdataconnector"

# Qualys API credentials
QUALYS_USERNAME="************"
QUALYS_PASSWORD="************"

# CSV file containing data for connectors
CSV_FILE_PATH="connector_data.csv"

# Log file
LOG_FILE="connector_creation.log"

# Delay between requests (in seconds)
DELAY_BETWEEN_REQUESTS=1

function log_info {
  local message=$1
  echo "$(date +'%Y-%m-%d %H:%M:%S') [INFO] $message" >> "$LOG_FILE"
  echo "[INFO] $message"
}

function log_error {
  local message=$1
  echo "$(date +'%Y-%m-%d %H:%M:%S') [ERROR] $message" >> "$LOG_FILE"
  echo "[ERROR] $message"
}

function create_connector {
  local name=$1
  local description=$2
  local application_id=$3
  local directory_id=$4
  local subscription_id=$5
  local authentication_key=$6

  # Remove unwanted characters from fields using awk
  name=$(echo "$name" | awk '{gsub(/[\r\n\t]/, ""); print}')
  description=$(echo "$description" | awk '{gsub(/[\r\n\t]/, ""); print}')
  application_id=$(echo "$application_id" | awk '{gsub(/[\r\n\t]/, ""); print}')
  directory_id=$(echo "$directory_id" | awk '{gsub(/[\r\n\t]/, ""); print}')
  subscription_id=$(echo "$subscription_id" | awk '{gsub(/[\r\n\t]/, ""); print}')
  authentication_key=$(echo "$authentication_key" | awk '{gsub(/[\r\n\t]/, ""); print}')

  # Construct JSON data
  json_data=$(cat <<EOF
{
  "ServiceRequest": {
    "data": {
      "AzureAssetDataConnector": {
        "name": "$name",
        "description": "$description",
        "activation": {
          "set": {
            "ActivationModule": [
              "VM",
              "PC"
            ]
          }
        },
        "disabled": false,
        "runFrequency": 240,
        "authRecord": {
          "applicationId": "$application_id",
          "directoryId": "$directory_id",
          "subscriptionId": "$subscription_id",
          "authenticationKey": "$authentication_key"
        },
        "connectorAppInfos": {
          "set": {
            "ConnectorAppInfoQList": [
              {
                "set": {
                  "ConnectorAppInfo": {
                    "name": "AI",
                    "identifier": "$subscription_id"
                  }
                }
              },
              {
                "set": {
                  "ConnectorAppInfo": {
                    "name": "CI",
                    "identifier": "$subscription_id"
                  }
                }
              },
              {
                "set": {
                  "ConnectorAppInfo": {
                    "name": "CSA",
                    "identifier": "$subscription_id"
                  }
                }
              }
            ]
          }
        }
      }
    }
  }
}
EOF
)

  # Make the API request using curl
  response=$(curl -s -u "$QUALYS_USERNAME:$QUALYS_PASSWORD" -H "Content-type: application/json" -X POST --data "$json_data" "$API_ENDPOINT")

  if [[ $? -eq 0 ]]; then
    if echo "$response" | grep -q '"responseCode":"SUCCESS"'; then
      log_info "Connector created successfully: $response"
    else
      log_error "Error creating connector: $response"
    fi
  else
    log_error "Error creating connector. Curl command failed."
  fi
}

function read_csv_and_create_connectors {
  log_info "Reading CSV and creating connectors..."

  # Use a while loop to read the CSV file line by line
  while IFS=, read -r name description application_id directory_id subscription_id authentication_key || [ -n "$name" ]; do
    if [ -n "$name" ] && [ "$name" != "name" ]; then
      log_info "Creating connector with Name: $name, Application ID: $application_id, Directory ID: $directory_id, Subscription ID: $subscription_id"
      create_connector "$name" "$description" "$application_id" "$directory_id" "$subscription_id" "$authentication_key"
      sleep $DELAY_BETWEEN_REQUESTS  # Add a delay between requests
    fi
  done < <(tail -n +2 "$CSV_FILE_PATH")  # Skip the header row

  log_info "CSV processing completed."
}

# Run the script
log_info "Script execution started."
read_csv_and_create_connectors
log_info "Script execution completed."
