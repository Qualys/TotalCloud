Here is a README file for the provided Bash script:


# Connector Scan Script

This script automates the process of scanning connectors for different cloud providers using the Qualys API. It supports Google Cloud Platform (GCP), Amazon Web Services (AWS), and Microsoft Azure.

## Prerequisites

- Bash shell
- `curl` command-line tool
- `jq` command-line JSON processor
- Qualys API credentials

## Setup

1. **Install Dependencies**

   Make sure `curl` and `jq` are installed on your system. You can install them using the following commands:

   ```sh
   sudo apt-get install curl jq   # For Debian-based systems
   sudo yum install curl jq       # For Red Hat-based systems
Set Qualys API Credentials

Replace the placeholder <> in the AUTH_HEADER variable with your base64-encoded Qualys API credentials.


AUTH_HEADER="Authorization: Basic <base64_encoded_credentials>"

Script Usage:

   Run the Script

      Execute the script using the following command:


      ./connector_scan.sh
Select Cloud Provider:

   When prompted, select the cloud provider you want to scan connectors for:

      1 for GCP
      2 for AWS
      3 for Azure

View Logs:

   The script logs its operations to connector_scan_log.txt. Check this file for details about the execution.

Scan History

   The script maintains a scan history in scan_history.txt. This file keeps track of previously scanned connectors to avoid redundant scans.

Script Workflow:

   Initialize Log File

      The script starts by initializing a log file with the current date and time.

   Fetch Connectors

      It fetches the list of connectors for the selected cloud provider using pagination.

   Check Scan History

      For each connector, the script checks if it has already been scanned by referring to scan_history.txt.

   Launch Perimeter Scan

      If a connector has not been scanned, the script launches a perimeter scan using the Qualys API. If the connector has been scanned, it reactivates the scan schedule.

   Log Scan Results

      The results of each scan are logged, and the scan details are appended to scan_history.txt.

Files
   connector_scan.sh: The main script file.
   connector_scan_log.txt: Log file for script operations.
   scan_history.txt: History file for tracking scanned connectors.


Notes
   Ensure that the Qualys API URL is correctly set in the QUALYS_API_URL variable.
   The script assumes a valid API response structure. Modify the parsing logic if the API response format changes.
   Handle API rate limits and errors appropriately in a production environment.

License
This script is licensed under the MIT License. See the LICENSE file for more details.
