import argparse
import json
import sys
import requests

API_ROOT = 'http://dev.cwwed-staging.com/api'
#API_ROOT = 'http://localhost:8000/api'

DESCRIPTION = """
NSEM utility for interaction with CWWED:
    - downloads Covered Data for a particular storm to CWWED
    - uploads the Post Storm Assessment (PSA) for a particular storm to CWWED
"""


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
    endpoint = '/nsem/{}/'.format(args['psa-id'])
    url = '{}{}'.format(API_ROOT, endpoint)
    response = requests.get(url)
    nsem_data = response.json()
    print(json.dumps(nsem_data, indent=2))


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
parser_cd.set_defaults(func=download_cd)

#
# process args
#

args = parser.parse_args()
if 'func' in args:
    args.func(vars(args))
else:
    parser.print_help(sys.stderr)
