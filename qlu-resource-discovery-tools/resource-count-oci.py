#!/usr/bin/env python3

# pylint: disable=invalid-name

""" Qualys : Resource Count : OCI """

# pip3 install oci

import argparse
import concurrent.futures
import csv
import inspect
import json
import os
import signal
import sys

# As a single script download, we do not publish a requirements.txt. Autodocument.

try:
    import oci
except ImportError:
    print("\nERROR: Missing required OCI SDK packages. Run the following command to install/upgrade:\n")
    print("pip3 install --upgrade oci")
    sys.exit(1)


version='2.8.0'


####
# Command Line Arguments
####


DEFAULT_MAX_WORKERS = min(32, (os.cpu_count() or 1) + 4)

parser = argparse.ArgumentParser(description = 'Count OCI Resources')
parser.add_argument(
    '--data',
    action = 'store_true',
    dest = 'data_mode',
    help = 'Count Data Security (Buckets, etc) resources (default: disabled)',
    default = False
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

if args.max_workers < 1 or args.max_workers > 255:
    print(f"ERROR: --max-workers {args.max_workers} out of range: [1 .. 255]")
    sys.exit(1)


####
# Configuration and Globals
####


delegation_token_file = '/etc/oci/delegation_token'
output_file           = 'oci-resources.csv'
output_file_log       = 'oci-resources-log.csv'
error_log_file        = 'oci-errors-log.txt'
padding = 6

# Map command-line arguments to counts to execute and display.
enabled = {
    'Virtual Machines':        True,
    'Container Hosts':         True,
    'Serverless Functions':    True,

    'Data Buckets':            args.data_mode,

}

totals = {
    'Virtual Machines':         0,
    'Container Hosts':          0,
    'Serverless Functions':     0,
    'Serverless Containers':    0,

    'Data Buckets':             0,

}

totals_log = []
errors_log = []


####
# Common Library Code
####


def signal_handler(_signal_received, _frame):
    """ Control-C """
    print("\nExiting")
    sys.exit(0)


def progress_print(resource_count, resource_type, region=''):
    """ Resource output """
    rc = str(resource_count).rjust(padding)
    # Split and join to remove multiple spaces when variables are empty.
    print(' '.join(f"- {rc} {resource_type} in {region}".split()))
    totals_log.append([resource_type, resource_count, region])


def verbose_print(details):
    """ Verbose output """
    if args.verbose_mode:
        print(f"\nDEBUG: {details}")


def error_print(details, compartment = ''):
    """ Error output """
    compartment  = f"Compartment: {compartment} " if compartment else ""
    try:
        function = f"{inspect.stack()[1].function}()"
    except Exception:  # pylint: disable=broad-exception-caught
        function = ''
    try:
        details = str(details).replace("\n", " ").replace("\r", " ")
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    print(f"\nERROR: {compartment}{function} {details}\n")
    errors_log.append(f"ERROR: {compartment}{function} {details}")

####
# Customized Library Code
####


# Subscriptions (aka OCI Compartments)


def get_oci_compartments(config, signer):
    """ Get a list of OCI Compartments """
    try:
        compartments = []
        identity_client = oci.identity.IdentityClient(config=config, signer=signer)
        get_compartment_response = identity_client.get_compartment(compartment_id=config['tenancy'])
        root_compartment = json.loads(str(get_compartment_response.data))
        root_compartment['compartment_id'] = root_compartment['id']
        compartments.append(root_compartment)
        verbose_print(f"root_compartment: {root_compartment}")
        response = identity_client.list_compartments(compartment_id=config['tenancy'], compartment_id_in_subtree=True, limit=1000)
        verbose_print(f"compartments: {response.data}")
        compartments.extend(json.loads(str(response.data)))
        while response.has_next_page:
            response = identity_client.list_compartments(compartment_id=config['tenancy'], compartment_id_in_subtree=True, limit=1000, page=response.next_page)
            verbose_print(f"compartments: {response.data}")
            compartments.extend(json.loads(str(response.data)))
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex)
        error_print("Error getting OCI Compartments.")
        error_print("Exiting...")
        sys.exit()
    verbose_print(f"compartments: {compartments}")
    return compartments


def get_oci_regions(config, signer):
    """ Get a list of OCI Regions """
    try:
        identity_client = oci.identity.IdentityClient(config, signer=signer)
        list_regions_response = identity_client.list_region_subscriptions(tenancy_id=config['tenancy'])
        regions = json.loads(str(list_regions_response.data))
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex)
        error_print("Error getting OCI Regions.")
        error_print("Exiting...")
    verbose_print(f"regions: {regions}")
    return regions


def config_for_region(config, region):
    """ Create or modify an OCI config with the specified region. """
    region_config = config
    if region_config:
        region_config['region'] = region['region_key']
    else:
        region_config = {'region': region['region_key']}
    return region_config


# Virtual Machines: Compute Instances and Container Hosts: OKE


def get_oci_instances_and_oke_instances(config, signer, compartment, regions):
    """ Get OCI Compute Instances and OKE Instances """
    for region in regions:
        instances = []
        instances_count = 0
        container_instances_count = 0
        linux_instances_count = 0
        try:
            search_client = oci.resource_search.ResourceSearchClient(config=config_for_region(config, region), signer=signer)
            response = search_client.search_resources(
                oci.resource_search.models.StructuredSearchDetails(
                    type="Structured",
                   query=f"query instance resources return allAdditionalFields where compartmentId = '{compartment['id']}' && lifeCycleState != 'TERMINATED' && lifeCycleState != 'TERMINATING'")
            )
            verbose_print(f"instances: {response.data}")
            instances = json.loads(str(response.data))['items']
            while response.has_next_page:
                response = search_client.search_resources(
                    oci.resource_search.models.StructuredSearchDetails(
                        type="Structured",
                        query=f"query instance resources return allAdditionalFields where compartmentId = '{compartment['id']}' && lifeCycleState != 'TERMINATED' && lifeCycleState != 'TERMINATING'"),
                    page=response.next_page
                )
                verbose_print(f"instances: {response.data}")
                instances.extend(json.loads(str(response.data))['items'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            error_print(f"Exception getting Instances in Region: {region}: {ex}", compartment['id'])
        core_client = oci.core.ComputeClient(config=config_for_region(config, region), signer=signer)
        for instance in instances:
            verbose_print(f"virtual_machine: {instance}")
            instances_count += 1
            if 'defined_tags' in instance and 'Oracle-Tags' in instance['defined_tags'] and instance['defined_tags']['Oracle-Tags']['CreatedBy'] == 'oke':
                container_instances_count += 1
            operating_system = get_oci_image_operating_system(core_client, instance['additional_details']['imageId'])
            if operating_system and 'win' not in operating_system.lower():
                linux_instances_count += 1

        if instances_count > 0 or args.verbose_mode:
            progress_print(resource_count=instances_count, resource_type='Virtual Machines [Compute]', region=region['region_name'])
            totals['Virtual Machines'] += instances_count

        if container_instances_count > 0 or args.verbose_mode:
            progress_print(resource_count=container_instances_count, resource_type='Container Hosts [OKE]', region=region['region_name'])
            totals['Container Hosts'] += container_instances_count


def get_oci_image_operating_system(core_client, image_id):
    """ Get OCI Compute Image """
    try:
        image = core_client.get_image(image_id=image_id)
        verbose_print(f"image: {image.data}")
        return image.data.operating_system
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(f"Exception getting Operating System for Image: {image_id}: {ex}")
        return ''


# Serverless Functions: FunctionsFunction (FunctionsApplication ?)


def get_oci_cloud_functions_function(config, signer, compartment, regions):
    """ Get OCI Cloud Functions """
    for region in regions:
        serverless_functions_count = 0
        try:
            search_client = oci.resource_search.ResourceSearchClient(config=config_for_region(config, region), signer=signer)
            query_text = f"query functionsfunction resources where compartmentId = '{compartment['id']}' && lifeCycleState != 'DELETED' && lifeCycleState != 'DELETING'"
            response = search_client.search_resources(
                oci.resource_search.models.StructuredSearchDetails(
                    type="Structured",
                    query=query_text)
            )
            verbose_print(f"functions: {response.data}")
            items = json.loads(str(response.data))['items']
            serverless_functions_count = len(items)
            while response.has_next_page:
                response = search_client.search_resources(
                    oci.resource_search.models.StructuredSearchDetails(
                        type="Structured",
                        query=query_text),
                    page=response.next_page
                )
                verbose_print(f"functions: {response.data}")
                serverless_functions_count += len(json.loads(str(response.data))['items'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            error_print(f"Exception getting Serverless Functions in Region: {region}: {ex}", compartment['id'])

        if serverless_functions_count > 0 or args.verbose_mode:
            progress_print(resource_count=serverless_functions_count, resource_type='Serverless Functions [Functions]', region=region['region_name'])
            totals['Serverless Functions'] += serverless_functions_count


def get_oci_buckets(config, signer, compartment, regions):
    """ Get OCI Buckets """
    for region in regions:
        buckets_count = 0
        try:
            search_client = oci.resource_search.ResourceSearchClient(config=config_for_region(config, region), signer=signer)
            response = search_client.search_resources(
                oci.resource_search.models.StructuredSearchDetails(
                    type="Structured",
                    query=f"query bucket resources where compartmentId = '{compartment['id']}' && lifeCycleState != 'TERMINATED' && lifeCycleState != 'TERMINATING'")
            )
            verbose_print(f"buckets: {response.data}")
            buckets_count = len(json.loads(str(response.data))['items'])
            while response.has_next_page:
                response = search_client.search_resources(
                    oci.resource_search.models.StructuredSearchDetails(
                        type="Structured",
                        query=f"query bucket resources where compartmentId = '{compartment['id']}' && lifeCycleState != 'TERMINATED' && lifeCycleState != 'TERMINATING'"),
                    page=response.next_page
                )
                verbose_print(f"buckets: {response.data}")
                buckets_count += len(json.loads(str(response.data))['items'])
        except Exception as ex:  # pylint: disable=broad-exception-caught
            error_print(f"Exception getting Buckets in Region: {region}: {ex}", compartment['id'])

        if buckets_count > 0 or args.verbose_mode:
            progress_print(resource_count=buckets_count, resource_type='Buckets', region=region['region_name'])
            totals['Data Buckets'] += buckets_count


####
# Main
####


def get_oci_resources(config, signer, compartment, regions):
    """ Get countable resources """
    exceptions = 0
    # If debug mode is disabled (default), run all functions concurrently with multithreading.
    # If debug mode is enabled, run all functions sequentially without multithreading.
    if args.debug_mode:
        if enabled['Virtual Machines'] or enabled['Container Hosts']:
            get_oci_instances_and_oke_instances(config, signer=signer, compartment=compartment, regions=regions)
            if enabled['Serverless Functions']:
                get_oci_cloud_functions_function(config, signer=signer, compartment=compartment, regions=regions)
        if enabled['Data Buckets']:
            get_oci_buckets(config, signer=signer, compartment=compartment, regions=regions)
    else:
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            if enabled['Virtual Machines'] or enabled['Container Hosts']:
                futures.append(executor.submit(get_oci_instances_and_oke_instances, config, compartment=compartment, signer=signer, regions=regions))
                if enabled['Serverless Functions']:
                    futures.append(executor.submit(get_oci_cloud_functions_function, config, signer=signer, compartment=compartment, regions=regions))
            if enabled['Data Buckets']:
                futures.append(executor.submit(get_oci_buckets, config, signer=signer, compartment=compartment, regions=regions))
        for future in concurrent.futures.as_completed(futures):
            if future.exception():
                exceptions += 1


def output_results(compartments):
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
        csv_writer.writerow(['Resource Type', 'Resource Count', 'Region'])
        for item in totals_log:
            csv_writer.writerow(item)

    # Error File
    if errors_log:
        with open(error_log_file, 'w', encoding='utf-8') as err_file:
            for error in errors_log:
                err_file.write(error + "\n")

    # Summary
    print(f"\nResults across {len(compartments)} OCI Compartments (script version: {version})\n")

    if enabled['Virtual Machines']:
        print(f"{str(totals['Virtual Machines']).rjust(padding)} Virtual Machines [Compute Instances]")
    if enabled['Container Hosts']:
        print(f"{str(totals['Container Hosts']).rjust(padding)} Container Hosts [OKE]")
    if enabled['Serverless Functions']:
        print(f"{str(totals['Serverless Functions']).rjust(padding)} Serverless Functions [Cloud Functions]")

    if enabled['Data Buckets']:
        print()
        print(f"{str(totals['Data Buckets']).rjust(padding)} Data Buckets (Public and Private) [Buckets]")

    if not args.data_mode:
        print("\nTo count Data Security (Buckets, Databases, etc) resources, rerun with '--data'")

    print(f"\nDetails written to {output_file} and {output_file_log}")

    if errors_log:
        print("\nExceptions occurred.")
        print(f"Review {error_log_file} or rerun with '--debug' to disable parallel processing and exit upon first error.")


def main():
    """ Calculon Compute! """
    try:
        config = oci.config.from_file(oci.config.DEFAULT_LOCATION, oci.config.DEFAULT_PROFILE)
        verbose_print(f"configuration: {config} from {oci.config.DEFAULT_LOCATION} using {oci.config.DEFAULT_PROFILE} profile")
    except Exception as ex:  # pylint: disable=broad-exception-caught
        error_print(ex)
        error_print("Error reading OCI configuration from default Location and Profile.")
        error_print("Exiting...")
        sys.exit(0)

    if os.path.isfile(delegation_token_file):
        with open(delegation_token_file, 'r', encoding='utf-8') as f:
            delegation_token = f.read().strip()
        try:
            signer = oci.auth.signers.InstancePrincipalsDelegationTokenSigner(
                delegation_token = delegation_token
            )
        except Exception as ex:  # pylint: disable=broad-exception-caught
            error_print(ex)
            error_print("Error authenticating via Delegation Token File.")
            error_print("Exiting...")
            sys.exit(0)
    else:
        try:
            signer = oci.signer.Signer(
                tenancy                   = config['tenancy'],
                user                      = config['user'],
                fingerprint               = config['fingerprint'],
                private_key_file_location = config.get('key_file'),
            )
        except Exception as ex:  # pylint: disable=broad-exception-caught
            error_print(ex)
            error_print("Error authenticating via Profile.")
            error_print("Exiting...")
            sys.exit(0)

    regions = get_oci_regions(config, signer)

    print("Getting OCI Compartments")
    compartments = get_oci_compartments(config, signer)
    print(f"\nFound {len(compartments)} Compartments:")
    for compartment in compartments:
        print(f"- {compartment['id']} - {compartment['name']}")

    print("\nGetting Countable Resources for each OCI Compartment ...")
    for compartment in compartments:
        print(f"\nScanning {compartment['id']} - {compartment['name']}")
        get_oci_resources(config, signer, compartment, regions)

    output_results(compartments)


if __name__ == "__main__":
    signal.signal(signal.SIGINT,signal_handler)
    main()
