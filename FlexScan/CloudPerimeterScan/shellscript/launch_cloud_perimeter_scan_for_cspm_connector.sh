#!/bin/bash

# Variables
QUALYS_API_URL="https://qualysguard.qg1.apps.qualys.ca"
AUTH_HEADER="Authorization: Basic <>"
LOG_FILE="connector_scan_log.txt"
SCAN_HISTORY_FILE="scan_history.txt"

# Initialize the log file
echo "Starting connector scan script at $(date)" > "$LOG_FILE"

# Function to fetch connectors with pagination
fetch_connectors() {
  local api_endpoint=$1
  local pageNo=$2
  local pageSize=$3
  curl --silent --location "$api_endpoint?pageNo=$pageNo&pageSize=$pageSize" --header "$AUTH_HEADER"
}

# Prompt user to select a cloud provider
echo "Select a cloud provider:"
echo "1. GCP"
echo "2. AWS"
echo "3. Azure"
read -p "Enter the number corresponding to your choice: " cloud_choice

# Set the API endpoint, scan title prefix, and cloud_service based on the user's choice
case $cloud_choice in
  1)
    cloud_provider="GCP"
    CONNECTORS_API_ENDPOINT="$QUALYS_API_URL/cloudview-api/rest/v1/gcp/connectors"
    cloud_service="compute_engine"
    ;;
  2)
    cloud_provider="AWS"
    CONNECTORS_API_ENDPOINT="$QUALYS_API_URL/cloudview-api/rest/v1/aws/connectors"
    cloud_service="ec2"
    ;;
  3)
    cloud_provider="Azure"
    CONNECTORS_API_ENDPOINT="$QUALYS_API_URL/cloudview-api/rest/v1/azure/connectors"
    cloud_service="vm"
    ;;
  *)
    echo "Invalid choice. Exiting."
    exit 1
    ;;
esac

# Fetch all connectors with pagination
pageNo=0
pageSize=50
all_connectors=()

while true; do
  echo "Fetching connectors - Page $pageNo" | tee -a "$LOG_FILE"
  connectors_response=$(fetch_connectors $CONNECTORS_API_ENDPOINT $pageNo $pageSize)
  
  # Log the raw response for debugging
  echo "Connectors response (Page $pageNo): $connectors_response" | tee -a "$LOG_FILE"
  
  # Check if the response contains content
  connectors=$(echo "$connectors_response" | jq -c '.content[]? | {name: .name, id: .connectorId}')
  
  if [ -z "$connectors" ]; then
    echo "No more connectors found." | tee -a "$LOG_FILE"
    break
  fi
  
  # Append the current page of connectors to the list of all connectors
  while IFS= read -r connector; do
    all_connectors+=("$connector")
  done < <(echo "$connectors")
  
  # Check if we have more pages
  totalPages=$(echo "$connectors_response" | jq -r '.totalPages')
  
  if [ "$pageNo" -ge "$totalPages" ]; then
    break
  fi
  
  # Move to the next page
  ((pageNo++))
done

# Function to check if a connector exists in the scan history file
connector_exists_in_history() {
  local connector_name=$1
  local connector_id=$2
  grep -q "^$cloud_provider,$connector_name,$connector_id," "$SCAN_HISTORY_FILE"
}

# Function to get the scan ID from the history file
get_scan_id_from_history() {
  local connector_name=$1
  local connector_id=$2
  grep "^$cloud_provider,$connector_name,$connector_id," "$SCAN_HISTORY_FILE" | cut -d',' -f6
}

# Loop through each connector and launch a perimeter scan if not already scanned
for connector in "${all_connectors[@]}"; do
  connector_name=$(echo "$connector" | jq -r '.name')
  connector_id=$(echo "$connector" | jq -r '.id')
  
  if connector_exists_in_history "$connector_name" "$connector_id"; then
    scan_id=$(get_scan_id_from_history "$connector_name" "$connector_id")
    echo "Connector '$connector_name' (ID: $connector_id) already scanned with Scan ID: $scan_id. Activating schedule." | tee -a "$LOG_FILE"
    
    # Activate the schedule for the existing scan
    activate_response=$(curl --silent --location --request POST "$QUALYS_API_URL/api/2.0/fo/schedule/scan/" \
      --header "X-Requested-With: Curl" \
      --header "Content-Type: application/x-www-form-urlencoded" \
      --header "$AUTH_HEADER" \
      --data-urlencode "action=update" \
      --data-urlencode "id=$scan_id" \
      --data-urlencode "active=1")

    # Log the activation response
    echo "Activation response for Scan ID '$scan_id': $activate_response" | tee -a "$LOG_FILE"
    
    continue
  fi
  
  echo "Launching perimeter scan for connector: $connector_name (ID: $connector_id)" | tee -a "$LOG_FILE"
  
  # Construct the scan title
  scan_title="${connector_name}"


  # Launch perimeter scan
  scan_response=$(curl --silent --location --request POST "$QUALYS_API_URL/api/2.0/fo/scan/cloud/perimeter/job/" \
    --header "X-Requested-With: curl" \
    --header "$AUTH_HEADER" \
    --data-urlencode "action=create" \
    --data-urlencode "module=vm" \
    --data-urlencode "active=1" \
    --data-urlencode "schedule=now" \
    --data-urlencode "cloud_provider=$(echo $cloud_provider | tr '[:upper:]' '[:lower:]')" \
    --data-urlencode "cloud_service=$cloud_service" \
    --data-urlencode "connector_name=$connector_name" \
    --data-urlencode "option_title=Initial Options" \
    --data-urlencode "scan_title=$scan_title" \
    $azure_params)

  # Log the raw scan response for debugging
  echo "Scan response for connector '$connector_name': $scan_response" | tee -a "$LOG_FILE"

  # Check if the scan was created successfully
  if echo "$scan_response" | grep -q "<TEXT>Scan has been created successfully</TEXT>"; then
    scan_id=$(echo "$scan_response" | grep -o "<VALUE>[0-9]\+" | sed 's/<[^>]*>//g')
    scan_date=$(date +%Y-%m-%d)
    echo "Scan successfully created for connector '$connector_name' with scan ID: $scan_id" | tee -a "$LOG_FILE"
    # Store the connector details in the scan history file
    echo "$cloud_provider,$connector_name,$connector_id,$scan_title,$scan_date,$scan_id" >> "$SCAN_HISTORY_FILE"
  else
    echo "Failed to create scan for connector '$connector_name'. Response: $scan_response" | tee -a "$LOG_FILE"
  fi
done

echo "Connector scan script completed at $(date)" | tee -a "$LOG_FILE"

