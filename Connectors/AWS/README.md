# AWS Asset Data Connector Creation Script

This script automates the creation of AWS Asset Data Connectors using the Qualys API. It reads connector data from a CSV file and sends requests to the Qualys API to create connectors accordingly.

## Prerequisites

- Bash shell
- cURL (Command-Line Tool and Library)
- Qualys API credentials (username and password)
- CSV file containing connector data (e.g., connector_data.csv)

## Usage
1. Clone the repository:
```bash
git clone https://github.com/Qualys/TotalCloud.git
```

2. Navigate to the script directory:
```bash
cd Connectors/AWS
```

3. Update the script with your Qualys API credentials:

QUALYS_USERNAME="your_username"
QUALYS_PASSWORD="your_password"

4. Configure the Qualys API endpoint in the script (if different from the default):

API_ENDPOINT="https://qualysapi.qg1.apps.qualys.ca/qps/rest/3.0/create/am/awsassetdataconnector"

5. Place your CSV file (connector_data.csv) in the same directory as the script.

6. Make the script executable:
```bash
chmod +x create_connectors.sh
```
7. Run the script:
```bash
./Create_AWS_Connector.sh
````

## Configuration
API_ENDPOINT: Qualys API endpoint for creating AWS Asset Data Connectors. You can configure this endpoint if your Qualys instance has a different API URL.
DELAY_BETWEEN_REQUESTS: Delay (in seconds) between API requests to avoid rate limiting.

## Logging
Logs are stored in the connector_creation.log file in the same directory as the script.

## Notes
The script skips the header row in the CSV file.
Adjust the DELAY_BETWEEN_REQUESTS variable to control the delay between API requests.

