#!/usr/bin/env python

import json
import os
import requests
import base64
import time
import logging
import yaml
from socket import error as SocketError, errno
from concurrent.futures import ThreadPoolExecutor

# Setup logging configuration
def setup_logging(default_path='./config/logging.yml', default_level=logging.INFO, env_key='LOG_CFG'):
    """Setup logging configuration"""
    log_dir = "/Applications/Splunk/bin/scripts/log"
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except FileExistsError:
            pass

    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)

# Setup HTTP session
def setup_http_session():
    global httpSession
    httpSession = requests.Session()

# Setup credentials
def setup_credentials(username, password):
    global httpCredentials
    usrPass = f"{username}:{password}"
    usrPassBytes = bytes(usrPass, "utf-8")
    httpCredentials = base64.b64encode(usrPassBytes).decode("utf-8")

# Function to handle API requests
def handle_api_request(url, method='GET', params=None, json_data=None):
    api_response = None
    retry_count = 0
    while not api_response:
        try:
            start = time.monotonic()
            if method == 'GET':
                api_response = httpSession.get(url, headers=headers, params=params, verify=True)
            elif method == 'POST':
                api_response = httpSession.post(url, headers=headers, params=params, json=json_data, verify=True)
            response_time = time.monotonic() - start
            logging.info(f"\n\nStatus code {api_response.status_code} for {url}\nResponse time: {response_time}\n\n")
            if api_response.status_code == 200:
                return api_response
            else:
                time.sleep(30)
                retry_count += 1
                if retry_count > retry_limit:
                    logging.warning(f"Retry Count Exceeded Code {api_response.status_code} on {method} {url}")
                    return None
        except Exception as e:
            logging.error(f"\nException Encountered\nError {e} {e.__class__.__name__}\n")
            retry_count += 1
            if retry_count > retry_limit:
                logging.warning(f"Retry Count Exceeded on {method} {url}")
                return None

# Function to fetch data for a specific cloud provider
def fetch_data_for_provider(provider):
    logger.info(f"Starting script for {provider}...")
    page_num = 0
    complete_list = False

    while not complete_list:
        url = f"{PLATFORM_URL}/cloudview-api/rest/v1/{provider}/connectors?pageNo={page_num}&pageSize=50"
        logger.debug(f"Account list URL: {url}")
        account_list_response = handle_api_request(url)
        if not account_list_response:
            error_count += 1
            continue

        logger.info(f"Status Code: {account_list_response.status_code}")
        response = json.loads(account_list_response.text)
        logger.debug(f"Response from connector lists: {response}")

        for account in response['content']:
            url2 = f"{PLATFORM_URL}/cloudview-api/rest/v1/{provider}/evaluations/{account[account_types[provider]]}?pageSize=300"
            logger.debug(f"Account list URL: {url2}")
            eval_response = handle_api_request(url2)
            if not eval_response:
                error_count += 1
                continue

            logger.info(f"Status Code: {eval_response.status_code}")
            eval_content = json.loads(eval_response.text)['content']
            logger.debug(f"Response from CID for Account {account[account_types[provider]]}: {eval_content}")

            try:
                for i in eval_content:
                    cid = int(i["controlId"])
                    criticality = str(i["criticality"])
                    remediation_url = f"{PLATFORM_URL}/cloudview/controls/cid-{cid}.html"
                    if int(i['passedResources']) > 0 or int(i['failedResources']) > 0:
                        resource_page = 0
                        resource_eval_list = []
                        while True:
                            url3 = f"{PLATFORM_URL}/cloudview-api/rest/v1/{provider}/evaluations/{account[account_types[provider]]}/resources/{cid}?pageNo={resource_page}&pageSize=100&filter=evaluatedOn%3A%5Bnow-{hours_back}h..now-1s%5D"
                            logger.info(f"Account {account[account_types[provider]]} CID URL: {url3}")
                            result_response = handle_api_request(url3)
                            if not result_response:
                                error_count += 1
                                break

                            logger.info(f"GET {url3} Response Code {result_response.status_code}")
                            resource_evaluation = json.loads(result_response.text)
                            logger.debug(f"Resource Evaluation = {resource_evaluation}")

                            if resource_evaluation['numberOfElements'] > 0:
                                if resource_evaluation['content']:
                                    resource_eval_list.extend(resource_evaluation['content'])

                                if resource_evaluation['last'] and resource_eval_list:
                                    logger.debug(f"Full List of CID Evaluations = {resource_eval_list}")
                                    count = len(resource_eval_list)
                                    logger.info(f"Account {account[account_types[provider]]} - Resource CID {cid} Evaluations Count - {count}")

                                    for evals in resource_eval_list:
                                        resource_content = evals.copy()
                                        resource_content["controlName"] = i["controlName"]
                                        resource_content["controlId"] = i["controlId"]
                                        resource_content["remediationURL"] = remediation_url
                                        resource_content["name"] = account["name"]
                                        resource_content["criticality"] = criticality
                                        print(json.dumps(resource_content))

                                    break  # Exit the loop after processing the resources

                                else:
                                    resource_page += 1
                            else:
                                logger.debug(f"No resources found for CID {cid}")
                                break  # Exit the loop if no resources found

            except Exception as e:
                logger.error(f"Error encountered: {e}")
                error_count += 1
                continue

            except SocketError as e:
                if e.errno != errno.ECONNRESET:
                    raise
                else:
                    continue

        if response['last']:
            logger.debug(f"Error Count on API Requests: {error_count}")
            complete_list = True
        else:
            page_num += 1

    logger.info(f"Script for {provider} completed.\n")


# Start main
setup_logging()
logger = logging.getLogger(__name__)

# Set Qualys API Credentials and URL
USERNAME = "******"
PASSWORD = "******"
PLATFORM_URL = "https://qualysguard.qg1.apps.qualys.ca" # Refer https://www.qualys.com/platform-identification/

# Tracking Variables
error_count = 0

# Set Retry Limit for API Calls
retry_limit = 5

# Set Time Space in hours for data collection
hours_back = 8

# Specify Cloud Service Providers
cloud_providers = ["aws", "azure", "gcp"]
account_types = {
    "aws": "awsAccountId",
    "azure": "subscriptionId",
    "gcp": "projectId"
}

# Setup API Session Credentials
setup_http_session()
setup_credentials(USERNAME, PASSWORD)

# Setup Headers for API Calls
headers = {
    'Accept': '*/*',
    'content-type': 'application/json',
    'Authorization': "Basic %s" % httpCredentials
}

# Run script for each cloud provider in parallel
with ThreadPoolExecutor() as executor:
    executor.map(fetch_data_for_provider, cloud_providers)
