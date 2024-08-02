# Qualys Connector Scan Script

This script automates the process of fetching Qualys CloudView connectors and launching perimeter scans for them if they haven't been scanned before. It supports pagination and detailed logging to ensure smooth operation and easy troubleshooting.

## Features

- Fetch connectors from Qualys CloudView API with pagination.
- Launch perimeter scans for connectors.
- Maintain a scan history to avoid redundant scans.
- Activate existing scans if a connector has already been scanned.
- Detailed logging for all operations.
- Progress bar to show the status of processing connectors.
- Configuration via `config.json`.

## Prerequisites

- Python 3.x
- `requests` library
- `tqdm` library

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/Qualys/TotalCloud.git
    cd FlexScan/CloudPerimeterScan/GCP/
    ```

2. Create a virtual environment (optional but recommended):
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3. Install the required Python packages:
    ```bash
    pip install requests tqdm
    ```

## Configuration

1. Create a `config.json` file in the root directory with the following content:
    ```json
    {
        "username": "your_username",
        "password": "your_password",
        "QUALYS_Platform_URL": "https://qualysguard.qg1.apps.qualys.ca"
    }
    ```

2. Ensure you have a `scan_history.csv` file in the root directory. If it doesn't exist, the script will create it for you with appropriate headers.

## Usage

Run the script using the following command:
```bash
python3 gcp_cspm_cps.py
```

## Log File
The script generates a log file connector_scan_log.txt that contains detailed logs of the script's execution.
Errors and significant events are logged with timestamps for easier troubleshooting.

## Scan History
The script maintains a scan_history.csv file to keep track of connectors that have been scanned.
If a connector is found in the history file, the script activates the existing scan schedule instead of creating a new scan.
Script Workflow

- Initialization:
  - Load configuration from config.json.
  - Initialize the log file and scan history file.

- Fetch Connectors:
  - Fetch connectors from the Qualys CloudView API with pagination.
  - Log the response and handle errors gracefully.

- Process Connectors:
  - For each connector, check if it exists in the scan history.
  - If already scanned, activate the existing scan schedule.
  - If not, launch a new perimeter scan and update the scan history.

- Logging:
  - Detailed logs are maintained for all operations.
  - Progress is displayed using the tqdm library.

## Error Handling
The script includes robust error handling for network requests and file operations.
Errors are logged in connector_scan_log.txt.

## Contributing
Contributions are welcome! Please open an issue or submit a pull request with your improvements.

## Author
Yash Jhunjhunwala (Senior Solutions Architect, Cloud Security)
