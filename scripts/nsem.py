import argparse
import sys

DESCRIPTION = """
NSEM utility for interaction with CWWED:
    - downloads Covered Data for a particular storm to CWWED
    - uploads the Post Storm Assessment (PSA) for a particular storm to CWWED
"""


def create_psa(args):
    print('creating psa...')
    print(args)


def upload_psa(args):
    print('uploading psa...')
    print(args)


def download_cd(args):
    print('downloading cd...')
    print(args)


parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter)
subparsers = parser.add_subparsers(title='Commands', help='Commands')

#
# psa
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
# cd
#

# download
parser_cd = subparsers.add_parser('download-cd', help='Download Covered Data')
parser_cd.add_argument("storm-id", help='The id for the storm', type=int)
parser_cd.set_defaults(func=download_cd)

#
# process args
#

args = parser.parse_args()
if 'func' in args:
    args.func(args)
else:
    parser.print_help(sys.stderr)
