from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class StaticStorage(S3Boto3Storage):
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    custom_domain = '%s.s3.amazonaws.com' % settings.AWS_STORAGE_BUCKET_NAME
    auto_create_bucket = True
    file_overwrite = False
    gzip = True


class ArchiveStorage(S3Boto3Storage):
    default_acl = 'private'
    access_key = settings.CWWED_ARCHIVES_ACCESS_KEY_ID
    secret_key = settings.CWWED_ARCHIVES_SECRET_ACCESS_KEY
    bucket_name = settings.AWS_ARCHIVE_BUCKET_NAME
    custom_domain = '%s.s3.amazonaws.com' % settings.AWS_ARCHIVE_BUCKET_NAME
    auto_create_bucket = True
