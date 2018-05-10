import os
import errno
import argparse
from urllib import parse
import boto3
import sys
import requests

API_ROOT = 'http://dev.cwwed-staging.com/api'

DESCRIPTION = """
NSEM utility for interaction with CWWED:
    - downloads Covered Data for a particular storm to CWWED
    - uploads the Post Storm Assessment (PSA) for a particular storm to CWWED
"""


def create_directory(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    return path


def create_psa(args):
    endpoint = '/nsem/'
    url = '{}{}'.format(API_ROOT, endpoint)
    headers = {
        'Authorization': 'Token {}'.format(args['api-token']),
    }
    data = {
        "named_storm": args['storm-id'],
    }
    # request a new post-storm assessment from the api
    response = requests.post(url, data=data, headers=headers)
    response.raise_for_status()
    nsem_data = response.json()
    print('Successfully created PSA version: {}'.format(nsem_data['id']))
    print('Packaging Covered Data. Please wait a few minutes before trying to download the data')


def upload_psa(args):
    print('uploading psa...')
    print(args)


def download_cd(args):
    # create the output directory if it's been declared
    output_dir = args['output_dir']
    if output_dir:
        create_directory(output_dir)
    else:
        output_dir = './'

    # query the api using a particular psa to find the object storage path for the Covered Data
    endpoint = '/nsem/{}/'.format(args['psa-id'])
    url = '{}{}'.format(API_ROOT, endpoint)
    response = requests.get(url)
    response.raise_for_status()
    nsem_data = response.json()

    # verify the "storage key" exists and points to an S3 object store
    # i.e s3://cwwed-archives/NSEM/Harvey/v76/Covered Data
    storage_key = 'covered_data_storage_url'
    if not nsem_data.get(storage_key) or not nsem_data[storage_key].startswith('s3://'):
        sys.exit('Covered Data is not ready for download yet.  Please try again.')
    else:
        # parse the s3 bucket and key from the "storage_key"
        parsed = parse.urlparse(nsem_data[storage_key])
        bucket = parsed.netloc
        path = parsed.path.lstrip('/')  # S3 paths are relative

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
parser_psa.set_defaults(func=lambda x: parser_psa.print_help())
subparsers_psa = parser_psa.add_subparsers(help='PSA sub-commands', dest='psa')

# psa - create
parser_psa_create = subparsers_psa.add_parser('create', help='Create a new PSA version')
parser_psa_create.add_argument("storm-id", help='The id for the storm', type=int)
parser_psa_create.add_argument("api-token", help='API token')
parser_psa_create.set_defaults(func=create_psa)

# psa - upload
parser_psa_upload = subparsers_psa.add_parser('upload', help='Upload a PSA')
parser_psa_upload.add_argument("file", help='The tar+gzipped post-storm assessment file to upload')
parser_psa_upload.add_argument("version", help='The version of this post-storm assessment', type=int)
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
