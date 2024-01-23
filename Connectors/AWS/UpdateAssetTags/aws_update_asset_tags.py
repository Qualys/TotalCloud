import os
import sys
import requests
import base64
import csv
import logging

# Qualys API endpoint Ref:- https://www.qualys.com/platform-identification/
QUALYS_API_ENDPOINT = '<API Server URL>'

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class QualysAPI:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + base64.b64encode(f"{username}:{password}".encode('utf-8')).decode('utf-8')
        }

    def make_api_request(self, endpoint, data, method='POST'):
        try:
            response = requests.request(method, endpoint, json=data, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error during API request to {endpoint}: {e}")
            return None

def search_aws_connectors(api, account_id):
    endpoint = f'{QUALYS_API_ENDPOINT}/qps/rest/3.0/search/am/awsassetdataconnector'
    data = {
        "ServiceRequest": {
            "filters": {
                "Criteria": [
                    {
                        "field": "awsAccountId",
                        "operator": "EQUALS",
                        "value": account_id
                    }
                ]
            }
        }
    }
    return api.make_api_request(endpoint, data)

def update_connector_tags(api, connector_id, tag_ids):
    endpoint = f'{QUALYS_API_ENDPOINT}/qps/rest/3.0/update/am/awsassetdataconnector/{connector_id}'
    data = {
        "ServiceRequest": {
            "data": {
                "AwsAssetDataConnector": {
                    "defaultTags": {
                        "set": {
                            "TagSimple": [{"id": tag_id} for tag_id in tag_ids]
                        }
                    }
                }
            }
        }
    }
    return api.make_api_request(endpoint, data, method='PUT')  # Adjusted method to 'PUT'

def read_account_tags_from_csv(csv_file):
    script_directory = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(script_directory, csv_file)

    account_tags = {}
    with open(csv_file_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            account_id = row.get('Account ID', '')
            tag_ids = [row.get(f'tagid{i}', '') for i in range(1, 10) if row.get(f'tagid{i}', '')]
            account_tags[account_id] = tag_ids
    return account_tags

if __name__ == "__main__":
    try:
        username = input("Enter Qualys API Username: ")
        password = input("Enter Qualys API Password: ")

        if not username or not password:
            logging.error("Invalid username or password. Exiting.")
            sys.exit(1)

        csv_file = "connector_data.csv"

        qualys_api = QualysAPI(username, password)

        account_tags = read_account_tags_from_csv(csv_file)

        for account_id, tag_ids in account_tags.items():
            result = search_aws_connectors(qualys_api, account_id)

            if result:
                count = result.get('ServiceResponse', {}).get('count', 0)

                if count == 0:
                    logging.info(f"No connectors found for Account ID {account_id} with the specified search criteria.")
                else:
                    logging.info(f"Search Result for Account ID {account_id}:")
                    connector_data = result.get('ServiceResponse', {}).get('data', [])

                    for connector in connector_data:
                        aws_connector = connector.get('AwsAssetDataConnector', {})
                        if aws_connector:
                            is_attached = aws_connector.get('isAttachedToOrgConnector', '').lower() == 'true'

                            if is_attached:
                                logging.warning(f"Skipping connector with ID {aws_connector.get('id')} as it is already attached to an org connector.")
                            else:
                                logging.info(f"Updating tags for connector with ID {aws_connector.get('id')}...")
                                update_result = update_connector_tags(qualys_api, aws_connector.get('id'), tag_ids)

                                if update_result:
                                    logging.info("Tags updated successfully.")
                                else:
                                    logging.error("Error updating tags.")

                            logging.info("\n" + "=" * 50 + "\n")  # Separating each result with a line
            else:
                logging.error(f"Error occurred during the API request for Account ID {account_id}.")

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
