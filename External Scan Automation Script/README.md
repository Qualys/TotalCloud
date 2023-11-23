## Qualys External Scan Automation Script
The Qualys External Scan Automation Script is a Python utility designed to streamline the process of launching external scans on public-facing cloud assets i.e for AWS, GCP, Azure, OCI . It leverages metadata collected by Qualys Connectors Application to automate the scan initiation process. This script is particularly useful for organizations using Qualys Connectors and Vulnerability management application.

## Prerequisites
Before using this script, make sure you have the following prerequisites in place:

- Python 3.x installed on your system.
- The requests library installed. You can install it using pip:
    - pip install requests
- A valid Qualys account with the necessary permissions to add IP addresses and launch scans.

## Usage
Follow these steps to use the script:

- Clone or download this repository to your local machine.
- Open a terminal or command prompt.
- Navigate to the directory where the script is located.
- Run the script using the following command:
- python LaunchExternalScanConnectors.py
- The script will prompt you for the following information:
    - Select a platform from the available options (e.g., US1, US2).
    - Enter your Qualys username and password.
    - Input a scan title and an option profile ID.
    - Specify the cloud type (AWS, GCP, or AZURE).
- The script will then make API requests to Qualys to fetch cloud resources, extract external IP addresses, add them to the module, and launch scans.
- The script will display success or error messages based on the outcome of the API requests.

## Customization
You can customize the script by modifying the platform_urls dictionary to include platform-specific QualysGuard and Qualys API URLs.
Ref:- https://www.qualys.com/platform-identification/

## Supported Cloud Types
AWS: Amazon Web Services
GCP: Google Cloud Platform
AZURE: Microsoft Azure
OCI: Oracle Cloud Infrastructure

## Disclaimer
This script is provided as-is and without warranty. Use it at your own risk, and ensure that you have the necessary permissions and credentials to access the Qualys API.

## Author
Yash Jhunjhunwala (Senior Solutions Architect, Cloud Security)
