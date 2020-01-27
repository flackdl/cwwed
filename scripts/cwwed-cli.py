#!/usr/bin/env python
import json
import os
import errno
import argparse
from getpass import getpass
from time import sleep
from urllib import parse
import sys
import requests
import threading
import boto3

API_ROOT_PROD = 'https://alpha.cwwed-staging.com/api/'
API_ROOT_LOCAL = 'http://localhost:8000/api/'

if os.environ.get('DEPLOY_STAGE') == 'local':
    print('>> In Development')
    API_ROOT = API_ROOT_LOCAL
else:
    API_ROOT = API_ROOT_PROD

ENDPOINT_COVERED_DATA_SNAPSHOT = 'named-storm-covered-data-snapshot/'
ENDPOINT_PSA = 'nsem-psa/'
ENDPOINT_AUTH = 'auth/'
ENDPOINT_STORMS = 'named-storm/'

COVERED_DATA_SNAPSHOT_WAIT_SECONDS = 5
COVERED_DATA_SNAPSHOT_ATTEMPTS = 30

S3_BUCKET = 'cwwed-archives'

DESCRIPTION = """
Utility for interacting with CWWED:
    - authenticate with CWWED
    - create a  Covered Data snapshot for a named storm
    - download a Covered Data snapshot for a named storm
    - upload a Post Storm Assessment for a named storm
    - list all Post Storm Assessments
"""


class ProgressPercentage:

    def __init__(self, filename, download_size=None):
        self._filename = filename
        self._size = float(os.path.getsize(filename)) if download_size is None else download_size
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            sys.stdout.write("\r%s  %s / %s  (%.2f%%)" % (
                self._filename, self._seen_so_far, self._size,
                percentage))
            sys.stdout.flush()


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


def list_covered_data_snapshots(args):
    url = os.path.join(API_ROOT, ENDPOINT_COVERED_DATA_SNAPSHOT)
    data = {
        "named_storm": args['storm-id'],
    }
    # request a new post-storm assessment from the api
    response = requests.get(url, data)
    snapshot_data = response.json()
    if not response.ok:
        print('ERROR')
        sys.exit(snapshot_data)
    else:
        print(json.dumps(snapshot_data, indent=2))


def create_covered_data_snapshot(args):
    url = os.path.join(API_ROOT, ENDPOINT_COVERED_DATA_SNAPSHOT)
    data = {
        "named_storm": args['storm-id'],
    }
    # request a new post-storm assessment from the api
    response = requests.post(url, data=data, headers=get_auth_headers(args['api-token']))
    snapshot_data = response.json()
    if not response.ok:
        print('ERROR')
        sys.exit(snapshot_data)
    else:
        print('Successfully created covered data snapshot record: {}'.format(snapshot_data['id']))
        print('Packaging covered data snapshot. This may take a few minutes. '
              'The email address associated with this account will be emailed when it is complete.')


def create_psa(args):
    url = os.path.join(API_ROOT, ENDPOINT_PSA)
    try:
        data = json.load(open(args['body'], 'r'))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        sys.exit(str(e))

    # upload the psa
    upload_psa(file=args['file'], path=data.get('path'))

    # request a new post-storm assessment from the api
    response = requests.post(url, json=data, headers=get_auth_headers(args['api-token']))
    nsem_data = response.json()
    if not response.ok:
        sys.exit(nsem_data)
    else:
        print('Successfully created PSA Id: {}'.format(nsem_data['id']))
        print("The email address associated with this account will be emailed when it's been extracted, validated and ingested.")


def get_aws_session():
    return boto3.Session(profile_name='nsem')


def upload_psa_intermediate_data(args):
    session = get_aws_session()
    s3 = session.resource('s3')
    s3_bucket = s3.Bucket(S3_BUCKET)
    directory = args['directory']
    for root, dirs, files in os.walk(directory):
        for file in files:
            path = os.path.join(root, file)
            s3_bucket.upload_file(
                path,
                os.path.join('NSEM/upload', path.lstrip('/')),
                ExtraArgs={
                    # TODO - uncomment to use glacier cold storage class
                    # 'StorageClass': 'GLACIER'
                },
                Callback=ProgressPercentage(path))
            print()


def upload_psa(file: str, path: str):

    # verify the "file" is of the correct type
    _, extension = os.path.splitext(file)
    if extension != '.tgz':
        sys.exit('File to upload must be ".tgz" (tar+gzipped)')

    # create the s3 resource
    session = get_aws_session()
    s3 = session.resource('s3')
    s3_bucket = s3.Bucket(S3_BUCKET)

    # upload the file to the specified path
    print('uploading {} to s3://{}/{}'.format(file, S3_BUCKET, path))
    s3_bucket.upload_file(file, path, Callback=ProgressPercentage(file))
    print('Successfully uploaded psa')


def fetch_psa(psa_id):
    # query the api using a particular psa to find the object storage path for the Covered Data
    url = '{}{}/'.format(
        os.path.join(API_ROOT, ENDPOINT_PSA),
        psa_id,
    )
    response = requests.get(url)
    response_json = response.json()
    if not response.ok:
        sys.exit(response_json)
    return response_json


def fetch_cd_snapshot(snapshot_id):
    # query the api using a particular snapshot
    url = '{}{}/'.format(
        os.path.join(API_ROOT, ENDPOINT_COVERED_DATA_SNAPSHOT),
        snapshot_id,
    )
    response = requests.get(url)
    response_json = response.json()
    if not response.ok:
        sys.exit(response_json)
    return response_json


def list_psa(args):
    print(json.dumps(fetch_psa(args['psa-id']), indent=2))


def download_cd(args):
    snapshot_id = args['snapshot-id']

    storage_key = 'covered_data_storage_url'

    # create the output directory if it's been declared
    output_dir = args['output_dir']
    if output_dir:
        create_directory(output_dir)
    else:
        output_dir = './Covered_Data_Snapshot-{}'.format(snapshot_id)

    # query the snapshot and see if the covered data has been packaged and ready for download.
    # sleep in between attempts for a limited amount of tries
    for _ in range(COVERED_DATA_SNAPSHOT_ATTEMPTS):

        # query the psa
        snapshot_data = fetch_cd_snapshot(snapshot_id)

        # verify it's complete, the "storage key" exists and points to an S3 object store
        # i.e s3://cwwed-archives/local/NSEM/Sandy/Covered Data Snapshots/9
        if not snapshot_data['date_completed'] or not snapshot_data.get(storage_key, '').startswith('s3://'):
            # Covered data isn't ready so print message and try again in a few seconds
            print('Covered Data is not ready for download yet.  Waiting...')
            sleep(COVERED_DATA_SNAPSHOT_WAIT_SECONDS)
        else:
            # success
            print('Covered Data found and will begin downloading...')
            break
    else:
        sys.exit('Covered Data still not ready. Please try again')

    #
    # the covered data is ready for download
    #

    # parse the s3 bucket and key from "storage_key"
    parsed = parse.urlparse(snapshot_data[storage_key])
    bucket = parsed.netloc
    path = parsed.path.lstrip('/')  # S3 paths are relative so remove leading slash

    # create the s3 instance
    session = get_aws_session()
    s3 = session.resource('s3')
    s3_bucket = s3.Bucket(bucket)

    # build a list of all the relevant files to download
    objects = []
    for obj in s3_bucket.objects.all():
        if obj.key.startswith(path):
            objects.append(obj)

    # download each file to out "output_dir"
    for obj in objects:
        dest_path = os.path.join(output_dir, obj.key)
        # create the directory and then download the file to the path
        create_directory(os.path.dirname(dest_path))
        s3_bucket.download_file(obj.key, dest_path, Callback=ProgressPercentage(dest_path, obj.size))
        print()

    print('Successfully downloaded Covered Data to {}'.format(output_dir))


def authenticate(*args):
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


def list_storms(*args):
    url = os.path.join(API_ROOT, ENDPOINT_STORMS)
    response = requests.get(url)
    if not response.ok:
        sys.exit(response)
    else:
        response = response.json()
        print(json.dumps(response, indent=2))


def search_storms(args):
    storm_name = args['name']
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
parser_auth = subparsers.add_parser('auth', help='Authenticate with username/password and receive token')
parser_auth.set_defaults(func=authenticate)

#
# Named Storm
#

parser_storm = subparsers.add_parser('storm', help='List and search storms')
parser_storm.set_defaults(func=lambda _: parser_storm.print_help())
subparsers_storm = parser_storm.add_subparsers(help='Storm sub-commands')

# search
parser_storm_search = subparsers_storm.add_parser('search', help='Search for a storm by name')
parser_storm_search.add_argument("name", help='The name of the storm')
parser_storm_search.set_defaults(func=search_storms)

# list
parser_storm_list = subparsers_storm.add_parser('list', help='List storms')
parser_storm_list.set_defaults(func=list_storms)


#
# Covered Data Snapshot
#

parser_cd = subparsers.add_parser('cd', help='Manage Covered Data Snapshots')
parser_cd.set_defaults(func=lambda _: parser_cd.print_help())
subparsers_cd = parser_cd.add_subparsers(help='Covered Data sub-commands', dest='cd')

# list
parser_cd_list = subparsers_cd.add_parser('list', help='List covered data snapshots for a storm')
parser_cd_list.set_defaults(func=list_covered_data_snapshots)
parser_cd_list.add_argument("storm-id", help='The id for the storm', type=int)

# create
parser_cd_create = subparsers_cd.add_parser('create', help='Create a new covered data snapshot')
parser_cd_create.set_defaults(func=create_covered_data_snapshot)
parser_cd_create.add_argument("storm-id", help='The id for the storm', type=int)
parser_cd_create.add_argument("api-token", help='API token')

# download
parser_cd_download = subparsers_cd.add_parser('download', help='Download a covered data snapshot')
parser_cd_download.add_argument("snapshot-id", help='The id of the covered data snapshot', type=int)
parser_cd_download.add_argument("--output-dir", help='The output directory')
parser_cd_download.set_defaults(func=download_cd)

#
# Post Storm Assessment
#

parser_psa = subparsers.add_parser('psa', help='Manage a Post Storm Assessment')
parser_psa.set_defaults(func=lambda _: parser_psa.print_help())
subparsers_psa = parser_psa.add_subparsers(help='PSA sub-commands', dest='psa')

# psa - create
parser_psa_create = subparsers_psa.add_parser('create', help='Create a new PSA version')
parser_psa_create.add_argument("body", help='The body json file describing the post storm assessment')
parser_psa_create.add_argument("file", help='The ".tgz" (tar+gzipped) post-storm assessment file to upload')
parser_psa_create.add_argument("api-token", help='API token')
parser_psa_create.set_defaults(func=create_psa)

# psa - list
parser_psa_list = subparsers_psa.add_parser('list', help='List a PSA')
parser_psa_list.add_argument("psa-id", help='The id of the post-storm assessment', type=int)
parser_psa_list.set_defaults(func=list_psa)

# psa - intermediate data
parser_psa_intermediate_data_upload = subparsers_psa.add_parser('upload-intermediate-data', help='Upload PSA Intermediate Data')
parser_psa_intermediate_data_upload.add_argument("psa-id", help='The id of the post-storm assessment', type=int)
parser_psa_intermediate_data_upload.set_defaults(func=upload_psa_intermediate_data)
parser_psa_intermediate_data_upload.add_argument("directory", help='The directory with the intermediate data to upload')


# process args
def process_args(args):

    if 'func' in args:
        args.func(vars(args))
    else:
        print(args)
        parser.print_help(sys.stderr)


if __name__ == '__main__':
    process_args(parser.parse_args())
