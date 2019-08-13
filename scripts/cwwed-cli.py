#!/usr/bin/env python
import json
import os
import errno
import argparse
from getpass import getpass
from time import sleep
from urllib import parse
import boto3
import sys
import requests

API_ROOT = 'https://dev.cwwed-staging.com/api/'
#API_ROOT = 'http://localhost:8000/api/'

ENDPOINT_NSEM = 'nsem-psa/'
ENDPOINT_AUTH = 'auth/'
ENDPOINT_STORMS = 'named-storms/'

COVERED_DATA_SNAPSHOT_WAIT_SECONDS = 5
COVERED_DATA_SNAPSHOT_ATTEMPTS = 30

DESCRIPTION = """
Utility for interacting with CWWED:
    - download Covered Data for a particular storm
    - upload a Post Storm Assessment (PSA) for a particular storm
"""


def create_directory(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    return path


def get_auth_headers(token):
    return {
        'Authorization': 'Token {}'.format(token),
    }


def create_psa(args):
    url = os.path.join(API_ROOT, ENDPOINT_NSEM)
    data = {
        "named_storm": args['storm-id'],
    }
    # request a new post-storm assessment from the api
    response = requests.post(url, data=data, headers=get_auth_headers(args['api-token']))
    nsem_data = response.json()
    if not response.ok:
        sys.exit(nsem_data)
    else:
        print('Successfully created PSA Id: {}'.format(nsem_data['id']))
        print('Packaging Covered Data. This may take a few minutes.  The email address associated with this account will be emailed when it is complete.')


def upload_psa(args):
    psa_id = args['psa-id']
    file = args['file']

    # query the psa
    nsem_data = fetch_psa(psa_id)

    # verify the covered data has been packaged (necessary for parsing bucket)
    if not nsem_data.get('covered_data_storage_url'):
        sys.exit('Error. Covered Data has not been packaged yet and nothing can be uploaded yet')

    # verify the "file" is of the correct type
    _, extension = os.path.splitext(file)
    if extension != '.tgz':
        sys.exit('File to upload must be ".tgz" (tar+gzipped)')

    # verify this record needs processing
    if nsem_data['model_output_snapshot_extracted']:
        sys.exit('Error.  This PSA cannot be updated since it has already been processed and extracted')

    # parse the s3 bucket from 'covered_data_storage_url'
    parsed = parse.urlparse(nsem_data['covered_data_storage_url'])
    bucket = parsed.netloc

    # create the s3 instance
    s3 = boto3.resource('s3')
    s3_bucket = s3.Bucket(bucket)

    # upload the file to the specified path
    upload_path = nsem_data['model_output_upload_path']
    print('uploading {} to {}'.format(file, upload_path))
    s3_bucket.upload_file(file, upload_path)
    print('Successfully uploaded file')

    # update the PSA record in CWWED to point to the uploaded file so it can be extracted
    print('Updating PSA record in CWWED to extract the PSA')
    url = '{}{}/'.format(
        os.path.join(API_ROOT, ENDPOINT_NSEM),
        psa_id,
    )
    data = {
        'model_output_snapshot': upload_path,
    }
    response = requests.patch(url, data=data, headers=get_auth_headers(args['api-token']))
    if not response.ok:
        sys.exit(response.json())
    else:
        print('Successfully updated PSA in CWWED')


def fetch_psa(psa_id):
    # query the api using a particular psa to find the object storage path for the Covered Data
    url = '{}{}/'.format(
        os.path.join(API_ROOT, ENDPOINT_NSEM),
        psa_id,
    )
    response = requests.get(url)
    response_json = response.json()
    if not response.ok:
        sys.exit(response_json)
    return response_json


def list_psa(args):
    print(json.dumps(fetch_psa(args['psa-id']), indent=2))


def download_cd(args):
    psa_id = args['psa-id']

    # create the output directory if it's been declared
    output_dir = args['output_dir']
    if output_dir:
        create_directory(output_dir)
    else:
        output_dir = './PSA-v{}-CD'.format(psa_id)

    # query the psa and see if the covered data has been packaged and ready for download.
    # sleep in between attempts for a limited amount of tries
    for _ in range(COVERED_DATA_SNAPSHOT_ATTEMPTS):

        # query the psa
        nsem_data = fetch_psa(psa_id)

        # verify the "storage key" exists and points to an S3 object store
        # i.e s3://cwwed-archives/NSEM/Harvey/v76/Covered Data
        storage_key = 'covered_data_storage_url'
        if not nsem_data.get(storage_key) or not nsem_data[storage_key].startswith('s3://'):
            # Covered data isn't ready so print message and try again in a few seconds
            print('Covered Data is not ready for download yet.  Waiting...')
            sleep(COVERED_DATA_SNAPSHOT_WAIT_SECONDS)
        else:
            # success
            print('Covered Data found and will begin downloading...')
            break
    else:
        sys.exit('Covered Data took too long to be packaged. Please try again')

    #
    # the covered data is ready for download
    #

    # parse the s3 bucket and key from "storage_key"
    parsed = parse.urlparse(nsem_data[storage_key])
    bucket = parsed.netloc
    path = parsed.path.lstrip('/')  # S3 paths are relative so remove leading slash

    # create the s3 instance
    s3 = boto3.resource('s3')
    s3_bucket = s3.Bucket(bucket)

    # build a list of all the relevant files to download
    files = []
    for obj in s3_bucket.objects.all():
        if obj.key.startswith(path):
            files.append(obj.key)

    # download each file to out "output_dir"
    for file in files:
        dest_path = os.path.join(output_dir, file)
        print('downloading {} to {}'.format(file, dest_path))
        # create the directory and then download the file to the path
        create_directory(os.path.dirname(dest_path))
        s3_bucket.download_file(file, dest_path)

    print('Successfully downloaded Covered Data to {}'.format(output_dir))


def authenticate(args):
    username = input('Username: ')
    password = getpass('Password: ')
    url = os.path.join(API_ROOT, ENDPOINT_AUTH)
    data = {
        "username": username,
        "password": password,
    }
    # retrieve token from user/pass
    response = requests.post(url, data=data)
    token_response = response.json()
    print(token_response)


def search_storms(args):
    storm_name = args['storm-name']
    url = os.path.join(API_ROOT, ENDPOINT_STORMS)
    data = {
        "search": storm_name,
    }
    response = requests.get(url, params=data)
    search_response = response.json()
    if not response.ok:
        sys.exit(search_response)
    else:
        print(json.dumps(search_response, indent=2))


############################
# parse arguments
############################

parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter)
subparsers = parser.add_subparsers(title='Commands', help='Commands')

#
# Auth
#

# authenticate and retrieve token
parser_cd = subparsers.add_parser('auth', help='Authenticate with username/password and receive token')
parser_cd.set_defaults(func=authenticate)

#
# Storms
#

# authenticate and retrieve token
parser_storm = subparsers.add_parser('search-storms', help='Search for a particular storm')
parser_storm.add_argument("storm-name", help='The name of the storm')
parser_storm.set_defaults(func=search_storms)

#
# Post Storm Assessment
#

parser_psa = subparsers.add_parser('psa', help='Manage a Post Storm Assessment')
parser_psa.set_defaults(func=lambda _: parser_psa.print_help())
subparsers_psa = parser_psa.add_subparsers(help='PSA sub-commands', dest='psa')

# psa - create
parser_psa_create = subparsers_psa.add_parser('create', help='Create a new PSA version')
parser_psa_create.add_argument("storm-id", help='The id for the storm', type=int)
parser_psa_create.add_argument("api-token", help='API token')
parser_psa_create.set_defaults(func=create_psa)

# psa - upload
parser_psa_upload = subparsers_psa.add_parser('upload', help='Upload a PSA product')
parser_psa_upload.add_argument("psa-id", help='The id of this post-storm assessment', type=int)
parser_psa_upload.add_argument("file", help='The ".tgz" (tar+gzipped) post-storm assessment file to upload')
parser_psa_upload.add_argument("api-token", help='API token')
parser_psa_upload.set_defaults(func=upload_psa)

# psa - list
parser_psa_list = subparsers_psa.add_parser('list', help='List a PSA')
parser_psa_list.add_argument("psa-id", help='The id of the post-storm assessment', type=int)
parser_psa_list.set_defaults(func=list_psa)

# psa - download covered data
parser_psa_download_cd = subparsers_psa.add_parser('download-cd', help='Download Covered Data for a particular PSA')
parser_psa_download_cd.add_argument("psa-id", help='The id for the psa', type=int)
parser_psa_download_cd.add_argument("--output-dir", help='The output directory')
parser_psa_download_cd.set_defaults(func=download_cd)

#
# process args
#

args = parser.parse_args()
if 'func' in args:
    args.func(vars(args))
else:
    print(args)
    parser.print_help(sys.stderr)
