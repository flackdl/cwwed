import os
import errno
import argparse
from time import sleep
from urllib import parse
import boto3
import sys
import requests

API_ROOT = 'http://dev.cwwed-staging.com/api/'
ENDPOINT_NSEM = 'nsem/'
COVERED_DATA_SNAPSHOT_WAIT_SECONDS = 5
COVERED_DATA_SNAPSHOT_ATTEMPTS = 30
NSEM_UPLOAD_BASE_PATH = 'NSEM/upload/'

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
    response.raise_for_status()
    nsem_data = response.json()
    print('Successfully created PSA Id: {}'.format(nsem_data['id']))
    print('Packaging Covered Data. This may take a few minutes')


def upload_psa(args):
    psa_id = args['psa-id']
    file = args['file']

    # query the psa
    nsem_data = get_psa(psa_id)

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

    # upload the file
    upload_path = os.path.join(
        NSEM_UPLOAD_BASE_PATH,
        'v{}.tgz'.format(nsem_data['id']),
    )
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
    response.raise_for_status()
    print('Successfully updated PSA in CWWED')


def get_psa(psa_id):
    # query the api using a particular psa to find the object storage path for the Covered Data
    url = '{}{}/'.format(
        os.path.join(API_ROOT, ENDPOINT_NSEM),
        psa_id,
    )
    response = requests.get(url)
    response.raise_for_status()
    nsem_data = response.json()

    return nsem_data


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
        nsem_data = get_psa(psa_id)

        # verify the "storage key" exists and points to an S3 object store
        # i.e s3://cwwed-archives/NSEM/Harvey/v76/Covered Data
        storage_key = 'covered_data_storage_url'
        if not nsem_data.get(storage_key) or not nsem_data[storage_key].startswith('s3://'):
            # Covered data isn't ready so print message and try again in a few seconds
            print('Covered Data is not ready for download yet.  Waiting...')
            sleep(COVERED_DATA_SNAPSHOT_WAIT_SECONDS)
        else:
            # success
            print('Success. Covered Data will begin downloading')
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


parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter)
subparsers = parser.add_subparsers(title='Commands', help='Commands')

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
parser_psa_upload = subparsers_psa.add_parser('upload', help='Upload a PSA')
parser_psa_upload.add_argument("psa-id", help='The id of this post-storm assessment', type=int)
parser_psa_upload.add_argument("file", help='The ".tgz" (tar+gzipped) post-storm assessment file to upload')
parser_psa_upload.add_argument("api-token", help='API token')
parser_psa_upload.set_defaults(func=upload_psa)

#
# Covered Data
#

# download
parser_cd = subparsers.add_parser('download-cd', help='Download Covered Data')
parser_cd.add_argument("psa-id", help='The id for the psa', type=int)
parser_cd.add_argument("--output-dir", help='The output directory')
parser_cd.set_defaults(func=download_cd)

#
# process args
#

args = parser.parse_args()
if 'func' in args:
    args.func(vars(args))
else:
    parser.print_help(sys.stderr)
