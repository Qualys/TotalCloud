import requests

# Define platform-specific QualysGuard and Qualys API URLs
platform_urls = {
    "US1": {
        "qualysguard_url": "https://qualysguard.qg1.apps.qualys.com",
        "qualysapi_url": "https://qualysapi.qg1.apps.qualys.com",
    },
    "US2": {
        "qualysguard_url": "https://qualysguard.qg2.apps.qualys.com",
        "qualysapi_url": "https://qualysapi.qg2.apps.qualys.com",
    },
    "US3": {
        "qualysguard_url": "https://qualysguard.qg3.apps.qualys.com",
        "qualysapi_url": "https://qualysapi.qg3.apps.qualys.com",
    },
    "US4": {
        "qualysguard_url": "https://qualysguard.qg4.apps.qualys.com",
        "qualysapi_url": "https://qualysapi.qg4.apps.qualys.com",
    },
    "EU1": {
        "qualysguard_url": "https://qualysguard.qg1.apps.qualys.eu",
        "qualysapi_url": "https://qualysapi.qg1.apps.qualys.eu",
    },
    "EU2": {
        "qualysguard_url": "https://qualysguard.qg2.apps.qualys.eu",
        "qualysapi_url": "https://qualysapi.qg2.apps.qualys.eu",
    },
    "IN1": {
        "qualysguard_url": "https://qualysguard.qg1.apps.qualys.in",
        "qualysapi_url": "https://qualysapi.qg1.apps.qualys.in",
    },
    "CA1": {
        "qualysguard_url": "https://qualysguard.qg1.apps.qualys.ca",
        "qualysapi_url": "https://qualysapi.qg1.apps.qualys.ca",
    },
    "AE1": {
        "qualysguard_url": "https://qualysguard.qg1.apps.qualys.ae",
        "qualysapi_url": "https://qualysapi.qg1.apps.qualys.ae",
    },
    "UK1": {
        "qualysguard_url": "https://qualysguard.qg1.apps.qualys.co.uk",
        "qualysapi_url": "https://qualysapi.qg1.apps.qualys.co.uk",
    },
    "AU1": {
        "qualysguard_url": "https://qualysguard.qg1.apps.qualys.com.au",
        "qualysapi_url": "https://qualysapi.qg1.apps.qualys.com.au",
    },
    "KSA1": {
        "qualysguard_url": "https://qualysguard.qg1.apps.qualysksa.com",
        "qualysapi_url": "https://qualysapi.qg1.apps.qualysksa.com",
    },
}

# Ask the user to select a platform
print("Available platforms:")
for platform in platform_urls.keys():
    print(f"- {platform}")

selected_platform = input("Enter the platform (e.g., US1): ")

# Check if the selected platform is valid
if selected_platform not in platform_urls:
    print("Invalid platform selection.")
else:
    # Get the selected platform's URLs
    urls = platform_urls[selected_platform]

    # User input for Qualys username and password
    username = input("Enter your Qualys username: ")
    password = input("Enter your Qualys password: ")

    # User input for scan title and option profile ID
    scan_title = input("Enter the scan title: ")
    option_id = input("Enter the option profile ID: ")

    # User input for cloud type (e.g., AWS, GCP, AZURE)
    cloud_type = input("Enter the cloud type (e.g., AWS, GCP, AZURE, OCI): ")

    # Define headers
    headers = {
        'X-Requested-With': 'Curl',
    }

    # Define the API endpoints based on the selected platform and cloud type
    if cloud_type.upper() == 'AWS':
        source_url = f'{urls["qualysguard_url"]}/cloudview-api/rest/v1/resource/EC2_INSTANCE/AWS'
    elif cloud_type.upper() == 'GCP':
        source_url = f'{urls["qualysguard_url"]}/cloudview-api/rest/v1/resource/VM_INSTANCE/GCP'
    elif cloud_type.upper() == 'AZURE':
        source_url = f'{urls["qualysguard_url"]}/cloudview-api/rest/v1/resource/VIRTUAL_MACHINE/Azure'
    elif cloud_type.upper() == 'OCI':
        source_url = f'{urls["qualysguard_url"]}/cloudview-api/rest/v1/resource/INSTANCE/oci'
    else:
        print("Invalid cloud type. Supported values are AWS, GCP, OCI and AZURE.")
        exit(1)

    destination_url = f'{urls["qualysapi_url"]}/api/2.0/fo/asset/ip/'
    scan_url = f'{urls["qualysapi_url"]}/api/2.0/fo/scan/'

    # Initialize variables for pagination
    page_number = 0
    page_size = 50
    total_pages = None

    # Initialize an empty list to store the results
    all_results = []

    try:
        while total_pages is None or page_number < total_pages:
            # Define the query parameters for pagination
            params = {
                'pageNo': page_number,
                'pageSize': page_size,
            }

            # Make the API request to source_url with authentication
            response = requests.get(source_url, headers=headers, params=params, auth=(username, password))

            # Check if the request was successful
            if response.status_code == 200:
                data = response.json()
                content = data.get('content', [])
                all_results.extend(content)

                # Check if there are more pages to fetch
                if not total_pages:
                    total_pages = data.get('totalPages', 1)

                # Increment the page number for the next request
                page_number += 1
            else:
                print(f"Error: {response.status_code} - {response.text}")
                break

        # Process the results and add external IP addresses to the module
        external_ip_addresses = []

        for result in all_results:
            if cloud_type.upper() == 'GCP':
                print(result)
                external_ip_address = result.get('externalIpAddress')
            elif cloud_type.upper() == 'AZURE':
                print(result)
                external_ip_address = result.get('primaryPublicIPAddress')
            elif cloud_type.upper() == 'OCI':
                vnic_dto = result.get('vnicDto', [])
                for vnic in vnic_dto:
                    external_ip_address = vnic.get('publicIp')
            else:
                external_ip_address = result.get('publicIpAddress')

            if external_ip_address:
                external_ip_addresses.append(external_ip_address)

        # Count the number of external IP addresses added to the module
        count = len(external_ip_addresses)
        print(f"Count of external IP addresses activated for VM: {count}")

        # Construct the data for the POST request to destination_url
        data = {
            'action': 'add',
            'enable_vm': 1,
            'ips': ','.join(external_ip_addresses),  # Comma-separated list of IP addresses
        }

        # Make the POST request to destination_url to add all external IP addresses
        response = requests.post(destination_url, headers=headers, data=data, auth=(username, password))

        # Check if the request was successful
        if response.status_code == 200:
            print("Added all external IP addresses to the module successfully.")
        else:
            print(f"Error adding external IP addresses to the module: {response.status_code} - {response.text}")

        # Launch a single external scan for all external IP addresses
        scan_data = {
            'action': 'launch',
            'scan_title': scan_title,
            'ip': ','.join(external_ip_addresses),  # Comma-separated list of IP addresses
            'option_id': option_id,
            'iscanner_name': 'External',
        }

        # Make the POST request to scan_url to launch the scan
        scan_response = requests.post(scan_url, headers=headers, data=scan_data, auth=(username, password))

        # Check if the scan request was successful
        if scan_response.status_code == 200:
            print(f"External scan '{scan_title}' launched for all external IP addresses.")
        else:
            print(f"Error launching external scan for all external IP addresses: {scan_response.status_code} - {scan_response.text}")

    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
