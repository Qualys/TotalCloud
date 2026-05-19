#!/usr/bin/env python3

# pylint: disable=invalid-name, too-many-lines

""" Qualys : Resource Count : AWS """

import argparse
import concurrent.futures
import csv
import inspect
import os
import signal
import sys

# As a single script download, we do not publish a requirements.txt. Autodocument.

try:
    import boto3
    import eks_token
    import kubernetes
    import urllib3
    from botocore.config import Config
except ImportError:
    print("\nERROR: Missing required AWS SDK packages. Run the following command to install/upgrade:\n")
    print("pip3 install --upgrade boto3 botocore eks_token kubernetes urllib3")
    sys.exit(1)


version='2.8.1'


####
# Command Line Arguments
####


DEFAULT_MAX_WORKERS = min(32, (os.cpu_count() or 1) + 4)

parser = argparse.ArgumentParser(description = 'Count AWS Resources')
parser.add_argument(
    '--all',
    action = 'store_true',
    dest = 'all',
    help = 'Count resources in all Accounts in the current AWS Organization (default: disabled)',
    default = False
)
parser.add_argument(
    '--id',
    dest = 'id',
    help = 'Count resources in the specified AWS Account (default: the ID of the current account)',
    default = None
)
parser.add_argument(
    '--accounts',
    action = 'store_true',
    dest = 'input_accounts',
    help = 'Count resources in the list of AWS Accounts (one ID per line) in a file named accounts.txt (default: disabled)',
    default = False
)
parser.add_argument(
    '--regions',
    action = 'store_true',
    dest = 'input_regions',
    help = 'Count resources in the list of AWS Regions (one per line) in a file named regions.txt (default: disabled)',
    default = False
)
parser.add_argument(
    '--role-name',
    action = 'store',
    dest = 'role_name',
    help = 'Specify the AWS IAM role name to use when assuming access to other AWS Accounts (default: OrganizationAccountAccessRole)',
    default = 'OrganizationAccountAccessRole'
)
parser.add_argument(
    '--data',
    action = 'store_true',
    dest = 'data_mode',
    help = 'Count Qualys Cloud Data Security (Buckets, Databases, etc) resources (default: disabled)',
    default = False
)
parser.add_argument(
    '--images',
    action = 'store_true',
    dest = 'images_mode',
    help = 'Count Qualys Cloud Registry Container Images (default: disabled)',
    default = False
)
parser.add_argument(
    '--ai',
    action = 'store_true',
    dest = 'ai_mode',
    help = 'Count AI/LLM resources (Bedrock Custom Models, Bedrock Agents) (default: disabled)',
    default = False
)
pgroup = parser.add_mutually_exclusive_group()
pgroup.add_argument(
    '--gov',
    action = 'store_true',
    dest = 'use_gov',
    help = 'Use GovCloud regions (default: disabled)',
    default = False
)
pgroup.add_argument(
    '--china',
    action = 'store_true',
    dest = 'use_china',
    help = 'Use China regions (default: disabled)',
    default = False
)
parser.add_argument(
    '--max-lambda-versions',
    action = 'store',
    dest = 'max_lambda_versions',
    help = 'Number of versions to count per Lambda Function (default: 5, range 0 to 10)',
    type = int,
    default = 5
)
parser.add_argument(
    '--max-image-tags',
    action = 'store',
    dest = 'max_image_tags',
    help = 'Number of image tags to count per registry image (default: 5, range 1 to 1000)',
    type = int,
    default = 5
)
parser.add_argument(
    '--max-workers',
    dest = 'max_workers',
    help = f'Maximum parallel processing requests (default: {DEFAULT_MAX_WORKERS}, range 1 to 255)',
    type = int,
    default = DEFAULT_MAX_WORKERS
)
parser.add_argument(
    '--debug',
    action = 'store_true',
    dest = 'debug_mode',
    help = 'Disable parallel processing and exit upon first error (default: disabled)',
    default = False
)
parser.add_argument(
    '--verbose',
    action = 'store_true',
    dest = 'verbose_mode',
    help = 'Output verbose debugging information (default: disabled)',
    default = False
)
args = parser.parse_args()

if args.max_lambda_versions < 0 or args.max_lambda_versions > 10:
    print(f"ERROR: --max-lambda-versions {args.max_lambda_versions} out of range: [0 .. 10]")
    sys.exit(1)
if args.max_image_tags < 1 or args.max_image_tags > 1000:
    print(f"ERROR: --max-image-tags {args.max_image_tags} out of range: [1 .. 1000]")
    sys.exit(1)
if args.max_workers < 1 or args.max_workers > 255:
    print(f"ERROR: --max-workers {args.max_workers} out of range: [1 .. 255]")
    sys.exit(1)


####
# Configuration and Globals
####

accounts_file   = 'accounts.txt'
regions_file    = 'regions.txt'
output_file     = 'aws-resources.csv'
output_file_log = 'aws-resources-log.csv'
error_log_file  = 'aws-errors-log.txt'
padding = 6

# Map command-line arguments to counts to execute and display.
enabled = {
    'Virtual Machines':             True,
    'Container Hosts':              True,
    'Serverless Functions':         True,
    'Serverless Containers':        True,

    'Data Buckets':                 args.data_mode,
    'PaaS Databases':               args.data_mode,
    'Data Warehouses':              args.data_mode,

    'Non-OS Disks':                 True,

    'Registry Container Images':    args.images_mode,

    'Bedrock Custom Models':        args.ai_mode,
    'Bedrock Agents':               args.ai_mode,

}

totals = {
    'Virtual Machines':              0,
    'Container Hosts':               0,
    'Serverless Functions':          0,
    'Serverless Containers':         0,

    'Data Buckets':                  0,
    'PaaS Databases':                0,
    'Data Warehouses':               0,

    'Non-OS Disks':                  0,
    'Registry Container Images':     0,

    'Bedrock Custom Models':         0,
    'Bedrock Agents':                0,

}

totals_log = []
errors_log = []


try:
    aws_api_config = Config(
        retries = {
            'max_attempts' : 10,
            'mode'         : 'adaptive'
        }
    )
except Exception as ex0:  # pylint: disable=broad-exception-caught
    print("\nERROR: ")
    print(ex0)
    print("Unable to authenticate. Please verify your configuration")
    sys.exit(1)


####
# Common Library Code
####


def signal_handler(_signal_received, _frame):
    """ Control-C """
    print("\nExiting")
    sys.exit(0)


def progress_print(resource_count, resource_type, account='', region='', details=''):
    """ Resource output """
    rc = str(resource_count).rjust(padding)
    # Split and join to remove multiple spaces when variables are empty.
    print(' '.join(f"- {rc} {resource_type} in {region} {details}".split()))
    totals_log.append([resource_type, resource_count, account, region])


def verbose_print(details):
    """ Verbose output """
    if args.verbose_mode:
        print(f"\nDEBUG: {details}")


def error_print(details, account=''):
    """ Error output """
    account  = f"Account: {account} " if account else ""
    try:
        function = f"{inspect.stack()[1].function}()"
    except Exception:  # pylint: disable=broad-exception-caught
        function = ''
    try:
        details = str(details).replace("\n", " ").replace("\r", " ")
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    print(f"\nERROR: {account} {function} {details}\n")
    errors_log.append(f"ERROR: {account} {function} {details}")


####
# Customized Library Code
####


# Pagination:
# Some AWS services use NextToken, nextToken, Marker, or Marker/NextMarker:
# https://github.com/iann0036/aws-pagination-rules/blob/master/README.md
# See also: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/paginators.html


def select_default_region():
    """ Select the default region based upon environment (aws, aws-cn, aws-us-gov) """
    if args.use_gov:
        return 'us-gov-east-1'
    if args.use_china:
        return 'cn-north-1'
    return 'us-east-1'


def tag_in_tags(tag_key, tag_value, tags):
    """ Check for tag key and value """
    if not tags:
        return False
    for tag in tags:
        if tag['Key'] == tag_key and tag['Value'] == tag_value:
            return True
    return False


# Subscriptions (aka AWS Accounts)


def get_aws_organization():
    """ Get Active Accounts in an AWS Organization """
    root_account_id = None
    accounts = []
    RESTORE_AWS_STS_REGIONAL_ENDPOINTS = os.environ.pop('AWS_STS_REGIONAL_ENDPOINTS', None)
    try:
        os.environ['AWS_STS_REGIONAL_ENDPOINTS'] = 'regional'
        client = boto3.client('organizations', region_name=select_default_region(), config=aws_api_config)
        root_account_id = client.describe_organization()['Organization']['MasterAccountId']
        response = client.list_accounts()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex)
        error_print("Error getting AWS Organization.")
        if RESTORE_AWS_STS_REGIONAL_ENDPOINTS is None:
            del os.environ['AWS_STS_REGIONAL_ENDPOINTS']
        else:
            os.environ['AWS_STS_REGIONAL_ENDPOINTS'] = RESTORE_AWS_STS_REGIONAL_ENDPOINTS
        return root_account_id, accounts
    for account in response['Accounts']:
        verbose_print(f"account: {account}")
        if account['Status'] != 'ACTIVE':
            continue
        accounts.append(account)
    while 'NextToken' in response:
        response = client.list_accounts(NextToken=response['NextToken'])
        for account in response['Accounts']:
            verbose_print(f"account: {account}")
            if account['Status'] != 'ACTIVE':
                continue
            accounts.append(account)
    if RESTORE_AWS_STS_REGIONAL_ENDPOINTS is None:
        del os.environ['AWS_STS_REGIONAL_ENDPOINTS']
    else:
        os.environ['AWS_STS_REGIONAL_ENDPOINTS'] = RESTORE_AWS_STS_REGIONAL_ENDPOINTS
    return root_account_id, accounts


def get_aws_account():
    """ Get AWS Account (UserId, Account, Arn) """
    try:
        client = boto3.client('sts')
        account = client.get_caller_identity()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex)
        error_print("Error getting current AWS Account.")
    verbose_print(f"account: {account}")
    return account


def get_aws_accounts_from_file():
    """Get the list of AWS Accounts """
    accounts = []
    if os.path.isfile(accounts_file):
        try:
            with open(accounts_file, 'r', encoding='utf-8') as file:
                for line in file:
                    account_id = line.strip()
                    # Verify the AWS Account ID is 12 digits.
                    if account_id and account_id.isdigit() and len(account_id) == 12:
                        accounts.append({'Id': account_id, 'Name': account_id})
                    else:
                        print(f"Skipping invalid Account ID from {accounts_file}: {account_id}")
        except Exception as ex:  # pylint: disable=broad-exception-caught
            error_print(ex)
            print("Error getting AWS Accounts from file.")
            print("Exiting...")
            sys.exit(1)
    else:
        print("Input file does not exist.")
        print(f"Create a file named {accounts_file} and add each AWS Account ID to scan, one per line.")
        print("Exiting...")
        sys.exit(1)
    return accounts


def aws_get_credentials(target_account_id, current_account_id, root_account_id):
    """ Get AWS Credentials to access the target account """
    # pylint: disable=consider-using-in
    if target_account_id == current_account_id or target_account_id == root_account_id:
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            credentials = credentials.get_frozen_credentials()
            return {
                'AccessKeyId':     credentials.access_key,
                'SecretAccessKey': credentials.secret_key,
                'SessionToken':    credentials.token
            }
        except Exception as ex:  # pylint: disable=broad-exception-caught
            error_print(ex, target_account_id)
            return None
    try:
        client = boto3.client('sts', config=aws_api_config)
        aws_partition = "arn:aws:iam::"
        if args.use_gov:
            aws_partition = "arn:aws-us-gov:iam::"
        elif args.use_china:
            aws_partition = "arn:aws-cn:iam::"
        assumed_role_object = client.assume_role(
            # Example: arn:aws:iam::123456789012:role/MyRoleName
            RoleArn=aws_partition + str(target_account_id) + ':role/' + args.role_name,
            RoleSessionName='Session1'
        )
        credentials = assumed_role_object['Credentials']
        return {
            'AccessKeyId':     credentials['AccessKeyId'],
            'SecretAccessKey': credentials['SecretAccessKey'],
            'SessionToken':    credentials['SessionToken']
        }
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex, target_account_id)
        return None


def get_aws_regions(credentials):
    """ Get AWS Regions, using the "default" AWS region for the partition (aws, aws-cn, aws-us-gov) """
    client = get_aws_client('ec2', select_default_region(), credentials)
    try: # pylint: disable=broad-exception-caught
        response = client.describe_regions(AllRegions=False)
        regions = response['Regions']
        regions = sorted(regions, key=lambda d: d['RegionName'])
        verbose_print(f"regions: {regions}")
        return regions
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex)
        error_print("Error getting AWS Regions.")
        return []


def get_aws_lightsail_region_names(credentials):
    """ Get AWS Lightsail Regions, which are a subset of all AWS Regions """
    client = get_aws_client('lightsail', select_default_region(), credentials)
    try: # pylint: disable=broad-exception-caught
        response = client.get_regions()
        regions = response['regions']
        regions = sorted(region['name'] for region in regions)
        verbose_print(f"lightsail regions: {regions}")
        return regions
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex)
        error_print("Error getting AWS Lightsail Regions.")
        return []


def get_aws_regions_from_file():
    """Get the list of AWS Regions """
    regions = []
    if os.path.isfile(regions_file):
        try:
            with open(regions_file, 'r', encoding='utf-8') as file:
                for line in file:
                    region = line.strip()
                    regions.append({'RegionName': region})
        except Exception as ex:  # pylint: disable=broad-exception-caught
            error_print(ex)
            print("Error getting AWS Regions from file.")
            print("Exiting...")
            sys.exit(1)
    else:
        print("Regions file does not exist.")
        print(f"Create a file named {regions_file} and add each AWS Region to scan, one per line.")
        print("Exiting...")
        sys.exit(1)
    return regions


def get_aws_client(service, region, credentials):
    """ Return an AWS Client """
    try:
        client = boto3.client(
            service,
            region_name           = region,
            config                = aws_api_config,
            aws_access_key_id     = credentials['AccessKeyId'],
            aws_secret_access_key = credentials['SecretAccessKey'],
            aws_session_token     = credentials['SessionToken']
        )
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex)
        print("Error getting AWS Client.")
        print("Exiting...")
        sys.exit(1)
    return client


# Virtual Machines: EC2 Instances


def get_aws_ec2_instances(region, credentials, account):
    """ Get AWS EC2 Instances (and the number of non-os disks) in the specified Account and Region """
    instances_count = 0
    non_os_disks_count = 0
    linux_instances_count = 0
    client = get_aws_client('ec2', region, credentials)
    try:
        response = client.describe_instances(MaxResults=1000)
    except Exception as ex:  # pylint: disable=broad-exception-caught
        response = {}
        error_print(ex, account['Id'])
        return
    for reservation in response['Reservations']:
        if 'Instances' in reservation:
            for instance in reservation['Instances']:
                verbose_print(f"instance: {instance}")
                if instance['State']['Name'] == 'terminated':
                    continue
                if tag_in_tags('Vendor', 'Databricks', instance.get('Tags', {})):
                    verbose_print(f"Skipping Databricks instance: {instance['Tags']}")
                    continue
                instances_count += 1
                non_os_disks_count += get_aws_ec2_instance_non_os_disks_count(instance)
                if 'PlatformDetails' in instance and 'win' not in instance['PlatformDetails'].lower():
                    linux_instances_count += 1
    while 'NextToken' in response:
        try:
            response = client.describe_instances(NextToken=response['NextToken'], MaxResults=1000)
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        for reservation in response['Reservations']:
            if 'Instances' in reservation:
                for instance in reservation['Instances']:
                    verbose_print(f"instance: {instance}")
                    if instance['State']['Name'] == 'terminated':
                        continue
                    if tag_in_tags('Vendor', 'Databricks', instance.get('Tags', {})):
                        verbose_print(f"Skipping Databricks instance: {instance['Tags']}")
                        continue
                    instances_count += 1
                    non_os_disks_count += get_aws_ec2_instance_non_os_disks_count(instance)
                    if 'PlatformDetails' in instance and 'win' not in instance['PlatformDetails'].lower():
                        linux_instances_count += 1

    if instances_count > 0 or args.verbose_mode:
        progress_print(resource_count=instances_count, resource_type='Virtual Machines [EC2]', region=region, account=account['Name'], details=f"with {non_os_disks_count} Non-OS Disks")
        totals['Virtual Machines'] += instances_count
        totals['Non-OS Disks'] += non_os_disks_count


def get_aws_ec2_instance_non_os_disks_count(instance):
    """ Get the volume count for data volumes of the specified EC2 Instance """
    non_os_disks_count = 0
    if 'BlockDeviceMappings' in instance:
        if len(instance['BlockDeviceMappings']) > 0:
            root_volume = instance['BlockDeviceMappings'][0]['Ebs']['VolumeId']
            for volume in instance['BlockDeviceMappings']:
                if volume['Ebs']['VolumeId'] != root_volume:
                    non_os_disks_count += 1
    return non_os_disks_count


# Virtual Machines: LightSail Instances


def get_aws_lightsail_instances(region, credentials, account):
    """ Get AWS Lightsail Instances (and the number of non-os disks) in the specified Account """
    instances_count = 0
    non_os_disks_count = 0
    linux_instances_count = 0
    client = get_aws_client('lightsail', region, credentials)
    try:
        response = client.get_instances()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        response = {}
        error_print(ex, account['Id'])
        return
    for instance in response['instances']:
        verbose_print(f"instance: {instance}")
        if instance['resourceType'] != 'Instance':
            continue
        if instance['state']['name'] == 'terminated':
            continue
        instances_count += 1
        non_os_disks_count += get_aws_lightsail_non_os_disks_count(instance)
        if 'PlatformDetails' in instance and 'win' not in instance['PlatformDetails'].lower():
            linux_instances_count += 1
    while 'nextPageToken' in response:
        try:
            response = client.get_instances(pageToken=response['nextPageToken'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        for instance in response['instances']:
            verbose_print(f"instance: {instance}")
            if instance['resourceType'] != 'Instance':
                continue
            if instance['state']['name'] == 'terminated':
                continue
            instances_count += 1
            non_os_disks_count += get_aws_lightsail_non_os_disks_count(instance)
            if 'PlatformDetails' in instance and 'win' not in instance['PlatformDetails'].lower():
                linux_instances_count += 1

    if instances_count > 0 or args.verbose_mode:
        progress_print(resource_count=instances_count, resource_type='Virtual Machines [Lightsail]', region=region, account=account['Name'], details=f"with {non_os_disks_count} Non-OS Disks")
        totals['Virtual Machines'] += instances_count
        totals['Non-OS Disks'] += non_os_disks_count


def get_aws_lightsail_non_os_disks_count(instance):
    """ Get the volume count for data disks of the specified Lightsail Instance """
    non_os_disks_count = 0
    if 'hardware' in instance and 'disks' in instance['hardware']:
        for disk in instance['hardware']['disks']:
            if disk['isSystemDisk'] is True:
                continue
            if disk['isAttached'] is not True:
                continue
            non_os_disks_count += 1
    return non_os_disks_count


# Container Hosts: ECS


def get_aws_ecs_container_instances(region, credentials, account):
    """ Get AWS ECS Container Hosts in the specified Account """
    ecs_clusters = []
    ecs_instances_count = 0
    client = get_aws_client('ecs', region, credentials)
    try:
        response = client.list_clusters()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        response = {}
        error_print(ex, account['Id'])
        return
    ecs_clusters.extend(response['clusterArns'])
    while 'nextToken' in response:
        try:
            response = client.list_clusters(nextToken=response['nextToken'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        ecs_clusters.extend(response['clusterArns'])
    for cluster in ecs_clusters:
        try:
            response = client.list_container_instances(cluster=cluster)
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        ecs_instances_count += len(response['containerInstanceArns'])
        while 'nextToken' in response:
            try:
                response = client.list_container_instances(cluster=cluster, nextToken=response['nextToken'])
            except Exception as ex:  # pylint: disable=broad-exception-caught
                response = {}
                error_print(ex, account['Id'])
                continue
            ecs_instances_count += len(response['containerInstanceArns'])

    if ecs_instances_count > 0 or args.verbose_mode:
        progress_print(resource_count=ecs_instances_count, resource_type='Container Hosts [ECS]', region=region, account=account['Name'])
        totals['Container Hosts'] += ecs_instances_count


# Container Hosts: EKS

# pylint: disable=too-many-statements
def get_aws_eks_instances(region, credentials, account):
    """ Get AWS EKS Container Hosts in the specified Account """
    eks_clusters = []
    eks_instances_count = 0
    eks_containers_count = 0
    eks_client = get_aws_client('eks', region, credentials)
    try:
        response = eks_client.list_clusters()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        response = {}
        error_print(ex, account['Id'])
        return
    eks_clusters.extend(response['clusters'])
    while 'nextToken' in response:
        try:
            response = eks_client.list_clusters(nextToken=response['nextToken'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        eks_clusters.extend(response['clusters'])
    ec2_client = get_aws_client('ec2', region, credentials)
    # Search for instances with the 'kubernetes.io/cluster/<cluster-name>' tag per cluster.
    for cluster_name in eks_clusters:
        try:
            response = ec2_client.describe_instances(Filters=[{'Name': 'tag-key', 'Values': ['kubernetes.io/cluster/' + cluster_name]}])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        for reservation in response['Reservations']:
            if 'Instances' in reservation:
                for instance in reservation['Instances']:
                    verbose_print(f"instance: {instance}")
                    if instance['State']['Name'] == 'terminated':
                        continue
                    eks_instances_count += 1
        while 'NextToken' in response:
            try:
                response = ec2_client.describe_instances(Filters=[{'Name': 'tag-key', 'Values': ['kubernetes.io/cluster/' + cluster_name]}], NextToken=response['NextToken'])
            except Exception as ex:  # pylint: disable=broad-exception-caught
                response = {}
                error_print(ex, account['Id'])
                continue
            for reservation in response['Reservations']:
                if 'Instances' in reservation:
                    for instance in reservation['Instances']:
                        verbose_print(f"instance: {instance}")
                        if instance['State']['Name'] == 'terminated':
                            continue
                        eks_instances_count += 1
    # Search for Fargate profiles per cluster.
    for cluster_name in eks_clusters:
        try:
            fargate_profiles_response = eks_client.list_fargate_profiles(clusterName=cluster_name)
            fargate_profiles = fargate_profiles_response.get('fargateProfileNames', [])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            fargate_profiles = []
            error_print(ex, account['Id'])
            continue
        if fargate_profiles:
            eks_containers_count += get_aws_cluster_fargate_pod_count(eks_client, cluster_name, account)
        while 'NextToken' in response:
            try:
                fargate_profiles_response = eks_client.list_fargate_profiles(clusterName=cluster_name, NextToken=response['NextToken'])
                fargate_profiles = fargate_profiles_response.get('fargateProfileNames', [])
            except Exception as ex:  # pylint: disable=broad-exception-caught
                fargate_profiles = []
                error_print(ex, account['Id'])
                continue
            if fargate_profiles:
                eks_containers_count += get_aws_cluster_fargate_pod_count(eks_client, cluster_name, account)

    if eks_instances_count > 0 or args.verbose_mode:
        progress_print(resource_count=eks_instances_count, resource_type='Container Hosts [EKS]', region=region, account=account['Name'])
        totals['Container Hosts'] += eks_instances_count
    if eks_containers_count > 0 or args.verbose_mode:
        progress_print(resource_count=eks_containers_count, resource_type='Serverless Containers [EKS Fargate]', region=region, account=account['Name'])
        totals['Serverless Containers'] += eks_containers_count


def get_aws_cluster_fargate_pod_count(eks_client, cluster_name, account):
    """ Use a Kubernetes client to count pods running on Fargate """
    pod_count = 0
    # Unfortunately, the kubernetes-python client does not allow for inlining the TLS CA Certificate.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        cluster_token = eks_token.get_token(cluster_name)
        cluster_token = cluster_token['status']['token']
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex, account['Id'])
        error_print('Unable to get fargate cluster token. Using default count of 1', account['Id'])
        return 1
    try:
        cluster_data = eks_client.describe_cluster(name=cluster_name)
        cluster_data = cluster_data['cluster']
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex, account['Id'])
        error_print('Unable to describe fargate cluster. Using default count of 1', account['Id'])
        return 1
    kconfig = kubernetes.config.kube_config.Configuration(
        api_key = {'authorization': 'Bearer ' + cluster_token},
        host    = cluster_data['endpoint'],
    )
    kconfig.verify_ssl = False
    kubernetes_api_client = kubernetes.client.ApiClient(configuration=kconfig)
    kubernetes_client = kubernetes.client.CoreV1Api(api_client=kubernetes_api_client)
    try:
        pods = kubernetes_client.list_pod_for_all_namespaces(timeout_seconds=4, watch=False)
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex, account['Id'])
        error_print('Unable to list fargate pod. Using default count of 1', account['Id'])
        return 1
    for pod in pods.items:
        node_name = pod.spec.node_name
        if node_name and node_name.startswith('fargate'):
            pod_count +=1
    return pod_count


# Serverless Functions: Lambda Functions


def get_aws_lambda_functions(region, credentials, account):
    """ Get AWS Lambda Functions in the specified Account """
    serverless_functions_count = 0
    client = get_aws_client('lambda', region, credentials)
    try:
        response = client.list_functions(MaxItems=1000)
    except Exception as ex:  # pylint: disable=broad-exception-caught
        response = {}
        error_print(ex, account['Id'])
        return
    functions = response['Functions']
    serverless_functions_count += len(functions)
    while 'NextMarker' in response:
        try:
            response = client.list_functions(Marker=response['NextMarker'], MaxItems=1000)
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        functions.extend(response['Functions'])
        serverless_functions_count += len(response['Functions'])
    serverless_functions_versions_count = 0
    # Qualys inspects a default of 5 (new Tenants) up to 10 (via Settings) versions.
    if args.max_lambda_versions > 0:
        for function in functions:
            versions = get_aws_lambda_function_versions(account, region, credentials, function['FunctionArn'])
            versions_count = min(args.max_lambda_versions, len(versions))
            serverless_functions_versions_count += versions_count

    if serverless_functions_count > 0 or args.verbose_mode:
        serverless_functions_count += serverless_functions_versions_count
        progress_print(resource_count=serverless_functions_count, resource_type='Serverless Functions [Lambda]', region=region, account=account['Name'])
        totals['Serverless Functions'] += serverless_functions_count


# Serverless Functions: Lambda Function Versions


def get_aws_lambda_function_versions(account, region, credentials, function_arn):
    """ Get AWS Lambda Function Versions for the specified Function """
    versions = []
    client = get_aws_client('lambda', region, credentials)
    try:
        response = client.list_versions_by_function(FunctionName=function_arn, MaxItems=args.max_lambda_versions)
        versions.extend(response['Versions'])
        versions = [v for v in versions if v['Version'] != '$LATEST']
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex, account['Id'])
    return versions


# Serverless Containers: ECS Fargate


def get_aws_ecs_resources(region, credentials, account):
    """ Get AWS Fargate Containers in the specified Account """
    ecs_clusters = []
    ecs_containers_count = 0
    ecs_tasks_count = 0
    client = get_aws_client('ecs', region, credentials)
    try:
        response = client.list_clusters()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        response = {}
        error_print(ex, account['Id'])
        return
    ecs_clusters.extend(response['clusterArns'])
    while 'nextToken' in response:
        try:
            response = client.list_clusters(nextToken=response['nextToken'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        ecs_clusters.extend(response['clusterArns'])
    for cluster in ecs_clusters:
        try:
            response = client.list_tasks(cluster=cluster, launchType='FARGATE')
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        if response['taskArns']:
            describe_tasks_response = client.describe_tasks(cluster=cluster, tasks=response['taskArns'])
            for task in describe_tasks_response['tasks']:
                ecs_containers_count += len(task['containers'])
            ecs_tasks_count += len(describe_tasks_response['tasks'])
        while 'nextToken' in response:
            try:
                response = client.list_tasks(cluster=cluster, launchType='FARGATE', nextToken=response['nextToken'])
            except Exception as ex:  # pylint: disable=broad-exception-caught
                response = {}
                error_print(ex, account['Id'])
                continue
            if response['taskArns']:
                describe_tasks_response = client.describe_tasks(cluster=cluster, tasks=response['taskArns'])
                for task in describe_tasks_response['tasks']:
                    ecs_containers_count += len(task['containers'])
                ecs_tasks_count += len(describe_tasks_response['tasks'])

    if ecs_containers_count > 0 or args.verbose_mode:
        progress_print(resource_count=ecs_containers_count, resource_type='Serverless Containers [ECS Fargate]', region=region, account=account['Name'])
        totals['Serverless Containers'] += ecs_containers_count


# Serverless Containers: SageMaker Domains


def get_aws_sagemaker_domains(region, credentials, account):
    """ Get AWS SageMaker Domains in the specified Account """
    sagemaker_domains_count = 0
    client = get_aws_client('sagemaker', region, credentials)
    try:
        response = client.list_domains()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        response = {}
        error_print(ex, account['Id'])
        return
    sagemaker_domains_count += len(response['Domains'])
    while 'NextToken' in response:
        try:
            response = client.list_domains(NextToken=response['NextToken'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        sagemaker_domains_count += len(response['Domains'])

    if sagemaker_domains_count > 0 or args.verbose_mode:
        progress_print(resource_count=sagemaker_domains_count, resource_type='Serverless Containers [SageMaker Domains]', region=region, account=account['Name'])
        totals['Serverless Containers'] += sagemaker_domains_count


# Serverless Containers: SageMaker Endpoints


def get_aws_sagemaker_endpoints(region, credentials, account):
    """ Get AWS SageMaker Endpoints in the specified Account """
    sagemaker_endpoints_count = 0
    client = get_aws_client('sagemaker', region, credentials)
    try:
        response = client.list_endpoints()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        response = {}
        error_print(ex, account['Id'])
        return
    sagemaker_endpoints_count += len(response['Endpoints'])
    while 'NextToken' in response:
        try:
            response = client.list_endpoints(NextToken=response['NextToken'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        sagemaker_endpoints_count += len(response['Endpoints'])

    if sagemaker_endpoints_count > 0 or args.verbose_mode:
        progress_print(resource_count=sagemaker_endpoints_count, resource_type='Serverless Containers [SageMaker Endpoints]', region=region, account=account['Name'])
        totals['Serverless Containers'] += sagemaker_endpoints_count


# Registry Container Images: ECR

# Limits: 1000 container images per ECR repository
# args.max_image_tags is already lower.


def get_aws_ecr_images(region, credentials, account):
    """ Get AWS ECR Images in the specified Account """
    ecr_repositories = []
    container_registry_images_count = 0
    client = get_aws_client('ecr', region, credentials)
    try:
        response = client.describe_repositories()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex, account['Id'])
        return
    ecr_repositories.extend(response['repositories'])
    while 'nextToken' in response:
        try:
            response = client.describe_repositories(nextToken=response['nextToken'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        ecr_repositories.extend(response['repositories'])
    for repository in ecr_repositories:
        try:
            response = client.list_images(repositoryName=repository['repositoryName'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        container_registry_images_count += min(args.max_image_tags, len(response['imageIds']))
        while 'nextToken' in response:
            try:
                response = client.list_images(repositoryName=repository['repositoryName'], nextToken=response['nextToken'])
            except Exception as ex:  # pylint: disable=broad-exception-caught
                response = {}
                error_print(ex, account['Id'])
                continue
            container_registry_images_count += min(args.max_image_tags, len(response['imageIds']))

    if container_registry_images_count > 0 or args.verbose_mode:
        progress_print(resource_count=container_registry_images_count, resource_type='Registry Container Images [ECR]', region=region, account=account['Name'])
        totals['Registry Container Images'] += container_registry_images_count


# Data Buckets: S3 Buckets

# Limits: 10000 S3 Buckets per Account.


def get_aws_s3_buckets(region, credentials, account):
    """ Get AWS S3 Buckets in the specified Account """
    buckets_count = 0
    client = get_aws_client('s3', region, credentials)
    try:
        response = client.list_buckets()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex, account['Id'])
        return
    buckets_count += len(response['Buckets'])
    while 'NextToken' in response:
        try:
            response = client.list_buckets(NextToken=response['NextToken'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        buckets_count += len(response['Buckets'])
    buckets_count = min(buckets_count, 10000)

    if buckets_count > 0 or args.verbose_mode:
        progress_print(resource_count=buckets_count, resource_type='Data Buckets [S3]', region=region, account=account['Name'])
        totals['Data Buckets'] += buckets_count


# Data in PaaS Databases (PaaS): DocumentDB


def get_aws_docdb_clusters(region, credentials, account):
    """ Get AWS DocumentDB Clusters in the specified Account """
    database_clusters_count = 0
    client = get_aws_client('docdb', region, credentials)
    try:
        response = client.describe_db_clusters()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex, account['Id'])
        return
    database_clusters_count += len(response['DBClusters'])
    while 'Marker' in response:
        try:
            response = client.describe_db_instances(Marker=response['Marker'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        database_clusters_count += len(response['DBClusters'])

    if database_clusters_count > 0 or args.verbose_mode:
        progress_print(resource_count=database_clusters_count, resource_type='PaaS Databases [DocumentDB]', region=region, account=account['Name'])
        totals['PaaS Databases'] += database_clusters_count


# Data in PaaS Databases (PaaS): RDS Aurora (MySQL, PostgreSQL)


def get_aws_rds_aurora_clusters(region, credentials, account):
    """ Get AWS RDS Aurora Clusters in the specified Account """
    database_clusters_count = 0
    client = get_aws_client('rds', region, credentials)
    filters = [
        {'Name': 'engine', 'Values':
            ['aurora-mysql', 'aurora-postgresql']
        }
    ]
    try:
        response = client.describe_db_clusters(Filters=filters)
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex, account['Id'])
        return
    database_clusters_count += len(response['DBClusters'])
    while 'Marker' in response:
        try:
            response = client.describe_db_clusters(Filters=filters, Marker=response['Marker'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        database_clusters_count += len(response['DBClusters'])

    if database_clusters_count > 0 or args.verbose_mode:
        progress_print(resource_count=database_clusters_count, resource_type='PaaS Databases [RDS Aurora]', region=region, account=account['Name'])
        totals['PaaS Databases'] += database_clusters_count


# Data in PaaS Databases (PaaS): RDS (MariaDB, MSSQL, MySQL, Oracle, PostgreSQL)


def get_aws_rds_instances(region, credentials, account):
    """ Get AWS RDS Instances in the specified Account """
    database_instances_count = 0
    client = get_aws_client('rds', region, credentials)
    filters = [
        {'Name': 'engine', 'Values':
            ['mariadb', 'mysql', 'oracle-ee', 'oracle-ee-cdb', 'oracle-se2', 'oracle-se2-cdb', 'postgres', 'sqlserver-ee', 'sqlserver-ex', 'sqlserver-se', 'sqlserver-web']
        }
    ]
    try:
        response = client.describe_db_instances(Filters=filters)
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex, account['Id'])
        return
    database_instances_count += len(response['DBInstances'])
    while 'Marker' in response:
        try:
            response = client.describe_db_instances(Filters=filters, Marker=response['Marker'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        database_instances_count += len(response['DBInstances'])

    if database_instances_count > 0 or args.verbose_mode:
        progress_print(resource_count=database_instances_count, resource_type='PaaS Databases [RDS]', region=region, account=account['Name'])
        totals['PaaS Databases'] += database_instances_count


# Data in PaaS Databases (PaaS): RedShift


def get_aws_redshift_clusters(region, credentials, account):
    """ Get AWS RedShift Clusters in the specified Account """
    database_clusters_count = 0
    client = get_aws_client('redshift', region, credentials)
    try:
        response = client.describe_clusters()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex, account['Id'])
        return
    database_clusters_count += len(response['Clusters'])
    while 'Marker' in response:
        try:
            response = client.describe_clusters(Marker=response['Marker'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        database_clusters_count += len(response['Clusters'])

    if database_clusters_count > 0 or args.verbose_mode:
        progress_print(resource_count=database_clusters_count, resource_type='PaaS Databases [RedShift]', region=region, account=account['Name'])
        totals['PaaS Databases'] += database_clusters_count


# Data in Data Warehouses: DynamoDB

# Limits: 1000 DynamoDBs Table per region per account.


def get_aws_dynamodb_tables(region, credentials, account):
    """ Get AWS DynamoDB Tables in the specified Account """
    data_warehouses_count = 0
    client = get_aws_client('dynamodb', region, credentials)
    try:
        response = client.list_tables()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex, account['Id'])
        return
    data_warehouses_count += len(response['TableNames'])
    while 'LastEvaluatedTableName' in response:
        try:
            response = client.list_tables(ExclusiveStartTableName=response['LastEvaluatedTableName'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        data_warehouses_count += len(response['TableNames'])
    data_warehouses_count = min(data_warehouses_count, 10000)

    if data_warehouses_count > 0 or args.verbose_mode:
        progress_print(resource_count=data_warehouses_count, resource_type='Data Warehouses [DynamoDB]', region=region, account=account['Name'])
        totals['Data Warehouses'] += data_warehouses_count


# AI/LLM: Bedrock Custom Models


def get_aws_bedrock_custom_models(region, credentials, account):
    """ Get AWS Bedrock Custom Models in the specified Account and Region """
    bedrock_custom_models_count = 0
    client = get_aws_client('bedrock', region, credentials)
    try:
        response = client.list_custom_models()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        ex_str = str(ex)
        if any(s in ex_str for s in ('EndpointResolutionError', 'UnknownEndpointError', 'UnknownOperationException', 'Unknown operation', 'Unknown Operation')):
            return
        error_print(ex, account['Id'])
        return
    bedrock_custom_models_count += len(response.get('modelSummaries', []))
    while 'nextToken' in response:
        try:
            response = client.list_custom_models(nextToken=response['nextToken'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        bedrock_custom_models_count += len(response.get('modelSummaries', []))

    if bedrock_custom_models_count > 0 or args.verbose_mode:
        progress_print(resource_count=bedrock_custom_models_count, resource_type='Bedrock Custom Models', region=region, account=account['Name'])
        totals['Bedrock Custom Models'] += bedrock_custom_models_count


# AI/LLM: Bedrock Agents


def get_aws_bedrock_agents(region, credentials, account):
    """ Get AWS Bedrock Agents in the specified Account and Region """
    bedrock_agents_count = 0
    client = get_aws_client('bedrock-agent', region, credentials)
    try:
        response = client.list_agents()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        ex_str = str(ex)
        if any(s in ex_str for s in ('EndpointResolutionError', 'UnknownEndpointError', 'UnknownOperationException', 'Unknown operation', 'Unknown Operation')):
            return
        error_print(ex, account['Id'])
        return
    bedrock_agents_count += len(response.get('agentSummaries', []))
    while 'nextToken' in response:
        try:
            response = client.list_agents(nextToken=response['nextToken'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            response = {}
            error_print(ex, account['Id'])
            continue
        bedrock_agents_count += len(response.get('agentSummaries', []))

    if bedrock_agents_count > 0 or args.verbose_mode:
        progress_print(resource_count=bedrock_agents_count, resource_type='Bedrock Agents', region=region, account=account['Name'])
        totals['Bedrock Agents'] += bedrock_agents_count


####
# Main
####

# pylint: disable=too-many-branches, too-many-statements
def get_aws_resources(account, current_account_id, root_account_id):
    """ Get countable resources """
    exceptions = 0
    credentials = aws_get_credentials(account['Id'], current_account_id, root_account_id)
    verbose_print(f"credentials: {credentials}")
    if not credentials:
        print(f"Skipping {account['Id']} - {account['Name']}")
        return
    if args.input_regions:
        regions = get_aws_regions_from_file()
    else:
        regions = get_aws_regions(credentials)
    # Implement lightsail_regions as a subset of regions.
    if regions:
        lightsail_regions = get_aws_lightsail_region_names(credentials)
    else:
        lightsail_regions = []
    # If debug mode is disabled (default), run all functions concurrently with multithreading.
    # If debug mode is enabled, run all functions sequentially without multithreading.
    if args.debug_mode:
        # AWS APIs requiring a regional client.
        for region in regions:
            if enabled['Virtual Machines']:
                get_aws_ec2_instances(region=region['RegionName'], credentials=credentials, account=account)
                if region['RegionName'] in lightsail_regions:
                    get_aws_lightsail_instances(region=region['RegionName'], credentials=credentials, account=account)
            if enabled['Container Hosts']:
                get_aws_ecs_container_instances(region=region['RegionName'], credentials=credentials, account=account)
                get_aws_eks_instances(region=region['RegionName'], credentials=credentials, account=account)
            if enabled['Serverless Functions']:
                get_aws_lambda_functions(region=region['RegionName'], credentials=credentials, account=account)
            if enabled['Serverless Containers']:
                get_aws_ecs_resources(region=region['RegionName'], credentials=credentials, account=account)
                get_aws_sagemaker_domains(region=region['RegionName'], credentials=credentials, account=account)
                get_aws_sagemaker_endpoints(region=region['RegionName'], credentials=credentials, account=account)
            if enabled['PaaS Databases']:
                get_aws_docdb_clusters(region=region['RegionName'], credentials=credentials, account=account)
                get_aws_rds_aurora_clusters(region=region['RegionName'], credentials=credentials, account=account)
                get_aws_rds_instances(region=region['RegionName'], credentials=credentials, account=account)
                get_aws_redshift_clusters(region=region['RegionName'], credentials=credentials, account=account)
            if enabled['Data Warehouses']:
                get_aws_dynamodb_tables(region=region['RegionName'], credentials=credentials, account=account)
            if enabled['Registry Container Images']:
                get_aws_ecr_images(region=region['RegionName'], credentials=credentials, account=account)
            if enabled['Bedrock Custom Models']:
                get_aws_bedrock_custom_models(region=region['RegionName'], credentials=credentials, account=account)
            if enabled['Bedrock Agents']:
                get_aws_bedrock_agents(region=region['RegionName'], credentials=credentials, account=account)
        # S3 APIs using a global control plane, so we use the "default" partition region.
        if enabled['Data Buckets']:
            get_aws_s3_buckets(region=select_default_region(), credentials=credentials, account=account)
    else:
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            # AWS APIs requiring a regional client.
            for region in regions:
                if enabled['Virtual Machines']:
                    futures.append(executor.submit(get_aws_ec2_instances, region=region['RegionName'], credentials=credentials, account=account))
                    if region['RegionName'] in lightsail_regions:
                        futures.append(executor.submit(get_aws_lightsail_instances, region=region['RegionName'], credentials=credentials, account=account))
                if enabled['Container Hosts']:
                    futures.append(executor.submit(get_aws_ecs_container_instances, region=region['RegionName'], credentials=credentials, account=account))
                    futures.append(executor.submit(get_aws_eks_instances, region=region['RegionName'], credentials=credentials, account=account))
                if enabled['Serverless Functions']:
                    futures.append(executor.submit(get_aws_lambda_functions, region=region['RegionName'], credentials=credentials, account=account))
                if enabled['Serverless Containers']:
                    futures.append(executor.submit(get_aws_ecs_resources, region=region['RegionName'], credentials=credentials, account=account))
                    futures.append(executor.submit(get_aws_sagemaker_domains, region=region['RegionName'], credentials=credentials, account=account))
                    futures.append(executor.submit(get_aws_sagemaker_endpoints, region=region['RegionName'], credentials=credentials, account=account))
                if enabled['PaaS Databases']:
                    futures.append(executor.submit(get_aws_docdb_clusters, region=region['RegionName'], credentials=credentials, account=account))
                    futures.append(executor.submit(get_aws_rds_aurora_clusters, region=region['RegionName'], credentials=credentials, account=account))
                    futures.append(executor.submit(get_aws_rds_instances, region=region['RegionName'], credentials=credentials, account=account))
                    futures.append(executor.submit(get_aws_redshift_clusters, region=region['RegionName'], credentials=credentials, account=account))
                if enabled['Data Warehouses']:
                    futures.append(executor.submit(get_aws_dynamodb_tables, region=region['RegionName'], credentials=credentials, account=account))
                if enabled['Registry Container Images']:
                    futures.append(executor.submit(get_aws_ecr_images, region=region['RegionName'], credentials=credentials, account=account))
                if enabled['Bedrock Custom Models']:
                    futures.append(executor.submit(get_aws_bedrock_custom_models, region=region['RegionName'], credentials=credentials, account=account))
                if enabled['Bedrock Agents']:
                    futures.append(executor.submit(get_aws_bedrock_agents, region=region['RegionName'], credentials=credentials, account=account))
            # S3 APIs using a global control plane, so we use the "default" partition region.
            if enabled['Data Buckets']:
                futures.append(executor.submit(get_aws_s3_buckets, region=select_default_region(), credentials=credentials, account=account))
        for future in concurrent.futures.as_completed(futures):
            if future.exception():
                exceptions += 1


def output_results(accounts):
    """ Output results """
    # Summary File
    with open(output_file, 'w', encoding='utf-8', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['Resource Type', 'Resource Count'])
        for resource_type, resource_count in totals.items():
            csv_writer.writerow([resource_type, resource_count])
    # Log File
    with open(output_file_log, 'w', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['Resource Type', 'Resource Count', 'Account', 'Region'])
        for item in totals_log:
            csv_writer.writerow(item)

    # Error File
    if errors_log:
        with open(error_log_file, 'w', encoding='utf-8') as err_file:
            for error in errors_log:
                err_file.write(error + "\n")

    # Summary
    print(f"\nResults across {len(accounts)} AWS Accounts (script version: {version})\n")

    if enabled['Virtual Machines']:
        print(f"{str(totals['Virtual Machines']).rjust(padding)} Virtual Machines [EC2, LightSail]")
    if enabled['Container Hosts']:
        print(f"{str(totals['Container Hosts']).rjust(padding)} Container Hosts [ECS, EKS]")
    if enabled['Serverless Functions']:
        print(f"{str(totals['Serverless Functions']).rjust(padding)} Serverless Functions [Lambda]")
    if enabled['Serverless Containers']:
        print(f"{str(totals['Serverless Containers']).rjust(padding)} Serverless Containers [ECS and EKS Fargate, SageMaker Domains, SageMaker Endpoints]")

    if enabled['Data Buckets']:
        print()
        print(f"{str(totals['Data Buckets']).rjust(padding)} Data Buckets (Public and Private) [S3]")
    if enabled['PaaS Databases']:
        print(f"{str(totals['PaaS Databases']).rjust(padding)} PaaS Databases [DocumentDB, RDS, RedShift]")
    if enabled['Data Warehouses']:
        print(f"{str(totals['Data Warehouses']).rjust(padding)} Data Warehouses [DynamoDB]")

    if enabled['Non-OS Disks']:
        print()
        print(f"{str(totals['Non-OS Disks']).rjust(padding)} Non-OS Disks [EC2, LightSail]")
    if enabled['Registry Container Images']:
        print(f"{str(totals['Registry Container Images']).rjust(padding)} Registry Container Images [ECR]")

    if enabled['Bedrock Custom Models'] or enabled['Bedrock Agents']:
        print()
    if enabled['Bedrock Custom Models']:
        print(f"{str(totals['Bedrock Custom Models']).rjust(padding)} Bedrock Custom Models")
    if enabled['Bedrock Agents']:
        print(f"{str(totals['Bedrock Agents']).rjust(padding)} Bedrock Agents")

    if not args.data_mode:
        print()
        print("To count Data Security (Buckets, Databases, etc) resources, rerun with '--data'")
    if not args.images_mode:
        print()
        print("To count Registry Container Images, rerun with '--images'")
    if not args.ai_mode:
        print()
        print("To count AI/LLM resources, rerun with '--ai'")

    print(f"\nDetails written to {output_file} and {output_file_log}")

    if errors_log:
        print("\nExceptions occurred.")
        print(f"Review {error_log_file} or rerun with '--debug' to disable parallel processing and exit upon first error.")


def main():
    """ Calculon Compute! """
    root_account_id = None

    print("Getting the current AWS Account")
    current_account = get_aws_account()
    current_account_id = current_account['Account']
    if current_account['Arn'].endswith('root'):
        root_account_id = current_account['Account']
    if current_account_id == root_account_id:
        print(f"\nFound Management Account:\n-- {current_account_id} {current_account['Arn']}")
    else:
        print(f"\nFound Account:\n- {current_account_id}")

    if args.all:
        if current_account_id == root_account_id:
            print(f"ERROR: The current AWS Account ({current_account['Arn']}) is a root account.")
            print("Roles may not be assumed by root accounts, and AssumeRole is required to scan Organization Member Accounts.")
            print("Exiting...")
            sys.exit(1)
        print("\nGetting AWS Accounts in the current AWS Organization")
        org_root_account_id, accounts = get_aws_organization()
        if org_root_account_id:
            print(f"\nFound Management Account:\n-- {org_root_account_id}")
        print(f"\nFound {len(accounts)} Accounts:")
        for account in accounts:
            print(f"-- {account['Id']} - {account['Name']}")
        print('')

    elif args.input_accounts:
        if current_account_id == root_account_id:
            print(f"ERROR: The current AWS Account ({current_account['Arn']}) is a root account.")
            print("Roles may not be assumed by root accounts, and AssumeRole is required to scan other Accounts.")
            print("Exiting...")
            sys.exit(1)
        print(f"\nGetting AWS Accounts from file: {accounts_file}")
        accounts = get_aws_accounts_from_file()
        print(f"\nFound {len(accounts)} Accounts:")

    else:
        if args.id:
            if current_account_id == root_account_id and args.id != current_account_id:
                print(f"ERROR: The current AWS Account ({current_account['Arn']}) is a root account.")
                print("Roles may not be assumed by root accounts, and AssumeRole is required to scan other Accounts.")
                print("Exiting...")
                sys.exit(1)
            print(f"\nGetting AWS Account: {args.id}")
            accounts = [{'Id': args.id, 'Name': args.id}]
            if root_account_id == args.id:
                print(f"\nFound Management Account:\n-- {args.id}")
        else:
            accounts = [{'Id': current_account_id, 'Name': current_account_id}]

    print("\nGetting Countable Resources for each AWS Account ...")
    for account in accounts:
        print(f"\nScanning {account['Id']} - {account['Name']}")
        get_aws_resources(account, current_account_id, root_account_id)

    output_results(accounts)


####

if __name__ == "__main__":
    signal.signal(signal.SIGINT,signal_handler)
    main()
