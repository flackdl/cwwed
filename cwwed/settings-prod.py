from .settings import *

# django-storages
# http://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html
AWS_STORAGE_BUCKET_NAME = 'cwwed-dev'
AWS_S3_CUSTOM_DOMAIN = '%s.s3.amazonaws.com' % AWS_STORAGE_BUCKET_NAME
STATIC_URL = "https://%s/" % AWS_S3_CUSTOM_DOMAIN
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_IS_GZIPPED = True
AWS_S3_FILE_OVERWRITE = False
