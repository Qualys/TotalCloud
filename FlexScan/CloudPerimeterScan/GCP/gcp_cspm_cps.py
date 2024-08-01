import requests
import json
import datetime
import os
from tqdm import tqdm
import base64

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# Extract values from config
username = config['username']
password = config['password']
QUALYS_Platform_URL = config['QUALYS_Platform_URL']

# Create the authorization header
auth_string = f"{username}:{password}"
auth_header = base64.b64encode(auth_string.encode()).decode()
AUTH_HEADER = f"Basic {auth_header}"

# Variables
LOG_FILE = "connector_scan_log.txt"
SCAN_HISTORY_FILE = "scan_history.csv"

# Initialize the log file
def initialize_log_file():
    with open(LOG_FILE, 'w') as log_file:
        log_file.write(f"Starting connector scan script at {datetime.datetime.now()}\n")

initialize_log_file()

# Ensure the scan history file exists with headers
def initialize_scan_history_file():
    if not os.path.exists(SCAN_HISTORY_FILE):
        with open(SCAN_HISTORY_FILE, 'w') as history_file:
            history_file.write("cloud_provider,connector_name,connector_id,scan_title,scan_date,scan_id\n")

initialize_scan_history_file()

# Function to log messages with delimiters
def log_message(message, level="INFO"):
    with open(LOG_FILE, 'a') as log_file:
        log_file.write(f"{datetime.datetime.now()} | {level} | {message}\n")

# Function to fetch connectors with pagination
def fetch_connectors(api_endpoint, pageNo, pageSize):
    headers = {
        "Authorization": AUTH_HEADER
    }
    url = f"{api_endpoint}?pageNo={pageNo}&pageSize={pageSize}"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an error for bad status codes
    except requests.exceptions.RequestException as e:
        log_message(f"Failed to fetch connectors from {url}: {e}", "ERROR")
        return None
    return response.json()

# Set the API endpoint, scan title prefix, and cloud_service for GCP
cloud_provider = "GCP"
CONNECTORS_API_ENDPOINT = f"{QUALYS_Platform_URL}/cloudview-api/rest/v1/gcp/connectors"
cloud_service = "compute_engine"

# Fetch all connectors with pagination
pageNo = 0
pageSize = 50
all_connectors = []

while True:
    log_message(f"Fetching connectors - Page {pageNo}")
    connectors_response = fetch_connectors(CONNECTORS_API_ENDPOINT, pageNo, pageSize)
    
    if connectors_response is None:
        log_message("Stopping script due to fetch error.", "ERROR")
        break

    # Log the raw response for debugging
    log_message(f"Connectors response (Page {pageNo}): {json.dumps(connectors_response, indent=2)}")
    
    # Check if the response contains content
    connectors = connectors_response.get('content', [])
    
    if not connectors:
        log_message(f"No more connectors found on Page {pageNo}.")
        break
    
    # Append the current page of connectors to the list of all connectors
    all_connectors.extend(connectors)
    
    # Check if we have more pages
    totalPages = connectors_response.get('totalPages', 0)
    
    if pageNo >= totalPages - 1:  # Total pages are zero-indexed
        log_message(f"Reached the last page of connectors. Total pages: {totalPages}.")
        break
    
    # Move to the next page
    pageNo += 1

# Function to check if a connector exists in the scan history file
def connector_exists_in_history(connector_name, connector_id):
    try:
        with open(SCAN_HISTORY_FILE, 'r') as history_file:
            return any(f"{cloud_provider},{connector_name},{connector_id}," in line for line in history_file)
    except IOError as e:
        log_message(f"Error reading scan history file: {e}", "ERROR")
        return False

# Function to get the scan ID from the history file
def get_scan_id_from_history(connector_name, connector_id):
    try:
        with open(SCAN_HISTORY_FILE, 'r') as history_file:
            for line in history_file:
                if f"{cloud_provider},{connector_name},{connector_id}," in line:
                    return line.strip().split(',')[5]
    except IOError as e:
        log_message(f"Error reading scan history file: {e}", "ERROR")
    return None

# Loop through each connector and launch a perimeter scan if not already scanned
for connector in tqdm(all_connectors, desc="Processing connectors"):
    connector_name = connector.get('name')
    connector_id = connector.get('connectorId')
    
    if not connector_name or not connector_id:
        log_message(f"Skipping connector with missing name or ID. Connector data: {connector}", "ERROR")
        continue

    if connector_exists_in_history(connector_name, connector_id):
        scan_id = get_scan_id_from_history(connector_name, connector_id)
        if not scan_id:
            log_message(f"Scan ID not found in history for connector '{connector_name}' (ID: {connector_id}).", "ERROR")
            continue
        log_message(f"Connector '{connector_name}' (ID: {connector_id}) already scanned with Scan ID: {scan_id}. Activating schedule.")
        
        # Activate the schedule for the existing scan
        try:
            activate_response = requests.post(
                f"{QUALYS_Platform_URL}/api/2.0/fo/schedule/scan/",
                headers={
                    "X-Requested-With": "Curl",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": AUTH_HEADER
                },
                data={
                    "action": "update",
                    "id": scan_id,
                    "active": 1
                }
            )
            activate_response.raise_for_status()
            log_message(f"Activation response for Scan ID '{scan_id}': {activate_response.text}")
        except requests.exceptions.RequestException as e:
            log_message(f"Failed to activate scan schedule for Scan ID '{scan_id}': {e}", "ERROR")
        continue
    
    log_message(f"Launching perimeter scan for connector: {connector_name} (ID: {connector_id})")
    
    # Construct the scan title
    scan_title = connector_name

    # Launch perimeter scan
    try:
        scan_response = requests.post(
            f"{QUALYS_Platform_URL}/api/2.0/fo/scan/cloud/perimeter/job/",
            headers={
                "X-Requested-With": "curl",
                "Authorization": AUTH_HEADER
            },
            data={
                "action": "create",
                "module": "vm",
                "active": 1,
                "schedule": "now",
                "cloud_provider": cloud_provider.lower(),
                "cloud_service": cloud_service,
                "connector_name": connector_name,
                "option_title": "Initial Options",
                "scan_title": scan_title
            }
        )
        scan_response.raise_for_status()

        # Log the raw scan response for debugging
        log_message(f"Scan response for connector '{connector_name}': {scan_response.text}")

        # Check if the scan was created successfully
        if "<TEXT>Scan has been created successfully</TEXT>" in scan_response.text:
            scan_id = scan_response.text.split("<VALUE>")[1].split("</VALUE>")[0]
            scan_date = datetime.datetime.now().strftime("%Y-%m-%d")
            log_message(f"Scan successfully created for connector '{connector_name}' with scan ID: {scan_id}")
            # Store the connector details in the scan history file
            with open(SCAN_HISTORY_FILE, 'a') as history_file:
                history_file.write(f"{cloud_provider},{connector_name},{connector_id},{scan_title},{scan_date},{scan_id}\n")
        else:
            log_message(f"Failed to create scan for connector '{connector_name}'. Response: {scan_response.text}", "ERROR")
    except requests.exceptions.RequestException as e:
        log_message(f"Error launching scan for connector '{connector_name}' (ID: {connector_id}): {e}", "ERROR")

log_message(f"Connector scan script completed at {datetime.datetime.now()}")
