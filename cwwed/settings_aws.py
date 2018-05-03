from .settings import *
import os

# django-storages
# http://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html

# static storage
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'cwwed-static-assets')
STATIC_URL = "https://%s.s3.amazonaws.com/" % AWS_STORAGE_BUCKET_NAME
STATICFILES_STORAGE = 'cwwed.storage_backends.StaticStorage'

# custom file storage
DEFAULT_FILE_STORAGE = 'cwwed.storage_backends.ArchiveStorage'
AWS_ARCHIVE_BUCKET_NAME = 'cwwed-archives'
AWS_S3_ARCHIVE_DOMAIN = '%s.s3.amazonaws.com' % AWS_ARCHIVE_BUCKET_NAME
CWWED_ARCHIVES_ACCESS_KEY_ID = os.environ['CWWED_ARCHIVES_ACCESS_KEY_ID']
CWWED_ARCHIVES_SECRET_ACCESS_KEY = os.environ['CWWED_ARCHIVES_SECRET_ACCESS_KEY']
