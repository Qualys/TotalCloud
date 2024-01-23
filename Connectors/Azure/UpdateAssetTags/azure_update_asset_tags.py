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
    API_ENDPOINT = QUALYS_API_ENDPOINT  # Class attribute for API endpoint

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

class AzureConnectorUpdater:
    def __init__(self, api):
        self.api = api

    def search_azure_connectors(self, subscription_id):
        endpoint = f'{QualysAPI.API_ENDPOINT}/qps/rest/3.0/search/am/azureassetdataconnector'
        data = {
            "ServiceRequest": {
                "filters": {
                    "Criteria": [
                        {
                            "field": "authRecord.subscriptionId",
                            "operator": "EQUALS",
                            "value": subscription_id
                        }
                    ]
                }
            }
        }
        return self.api.make_api_request(endpoint, data)

    def update_connector_tags(self, connector_id, tag_ids):
        endpoint = f'{QualysAPI.API_ENDPOINT}/qps/rest/3.0/update/am/azureassetdataconnector/{connector_id}'
        data = {
            "ServiceRequest": {
                "data": {
                    "AzureAssetDataConnector": {
                        "defaultTags": {
                            "set": {
                                "TagSimple": [{"id": tag_id} for tag_id in tag_ids]
                            }
                        }
                    }
                }
            }
        }
        return self.api.make_api_request(endpoint, data, method='PUT')  # Adjusted method to 'PUT'

def read_subscription_tags_from_csv(csv_file):
    script_directory = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(script_directory, csv_file)

    subscription_tags = {}
    with open(csv_file_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            subscription_id = row.get('SUBSCRIPTION ID', '')
            tag_ids = [row.get(f'tagid{i}', '') for i in range(1, 10) if row.get(f'tagid{i}', '')]
            subscription_tags[subscription_id] = tag_ids
    return subscription_tags

if __name__ == "__main__":
    try:
        username = input("Enter Qualys API Username: ")
        password = input("Enter Qualys API Password: ")

        if not username or not password:
            logging.error("Invalid username or password. Exiting.")
            sys.exit(1)

        csv_file = "connector_data.csv"

        qualys_api = QualysAPI(username, password)
        azure_connector_updater = AzureConnectorUpdater(qualys_api)

        subscription_tags = read_subscription_tags_from_csv(csv_file)

        for subscription_id, tag_ids in subscription_tags.items():
            result = azure_connector_updater.search_azure_connectors(subscription_id)

            if result:
                count = result.get('ServiceResponse', {}).get('count', 0)

                if count == 0:
                    logging.info(f"No Azure connectors found for Subscription ID {subscription_id}.")
                else:
                    logging.info(f"Search Result for Subscription ID {subscription_id}: {count} connector(s) found.")
                    connector_data = result.get('ServiceResponse', {}).get('data', [])

                    for connector in connector_data:
                        azure_connector = connector.get('AzureAssetDataConnector', {})
                        if azure_connector:
                            is_attached = azure_connector.get('isAttachedToOrgConnector', '').lower() == 'true'

                            if is_attached:
                                logging.warning(f"Skipping connector with ID {azure_connector.get('id')} as it is already attached to an org connector.")
                            else:
                                logging.info(f"Updating tags for connector with ID {azure_connector.get('id')}...")
                                update_result = azure_connector_updater.update_connector_tags(azure_connector.get('id'), tag_ids)

                                if update_result:
                                    logging.info("Tags updated successfully.")
                                else:
                                    logging.error("Error updating tags.")

                            logging.info("\n" + "=" * 50 + "\n")  # Separating each result with a line
            else:
                logging.error(f"Error occurred during the API request for Subscription ID {subscription_id}.")

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
