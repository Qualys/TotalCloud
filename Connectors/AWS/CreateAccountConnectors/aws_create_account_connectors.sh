#!/bin/bash

# Qualys API endpoint for creating AWS Connector. Ref:- https://www.qualys.com/platform-identification/
API_ENDPOINT="<Qualys_API_Server_URL>/qps/rest/3.0/create/am/awsassetdataconnector"

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
  local arn=$3
  local external_id=$4

  # Remove unwanted characters from fields using awk
  name=$(echo "$name" | awk '{gsub(/[\r\n\t]/, ""); print}')
  description=$(echo "$description" | awk '{gsub(/[\r\n\t]/, ""); print}')
  arn=$(echo "$arn" | awk '{gsub(/[\r\n\t]/, ""); print}')
  external_id=$(echo "$external_id" | awk '{gsub(/[\r\n\t]/, ""); print}')

  # Construct JSON data
  json_data=$(cat <<EOF
{
  "ServiceRequest": {
    "data": {
      "AwsAssetDataConnector": {
        "name": "$name",
        "description": "$description",
        "activation": {
          "set": {
            "ActivationModule": ["VM", "PC"]
          }
        },
        "disabled": false,
        "arn": "$arn",
        "externalId": "$external_id",
        "allRegions": true,
        "runFrequency": 240,
        "isRemediationEnabled": false,
        "connectorAppInfos": {
          "set": {
            "ConnectorAppInfoQList": [
              {"set": {"ConnectorAppInfo": {"name": "AI", "identifier": "$arn"}}},
              {"set": {"ConnectorAppInfo": {"name": "CI", "identifier": "$arn"}}},
              {"set": {"ConnectorAppInfo": {"name": "CSA", "identifier": "$arn"}}}
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
  while IFS=, read -r name description arn external_id || [ -n "$name" ]; do
    if [ -n "$name" ] && [ "$name" != "name" ]; then
      log_info "Creating connector with Name: $name, Arn: $arn, External ID: $external_id"
      create_connector "$name" "$description" "$arn" "$external_id"
      sleep $DELAY_BETWEEN_REQUESTS  # Add a delay between requests
    fi
  done < <(tail -n +2 "$CSV_FILE_PATH")  # Skip the header row

  log_info "CSV processing completed."
}

# Run the script
log_info "Script execution started."
read_csv_and_create_connectors
log_info "Script execution completed."
