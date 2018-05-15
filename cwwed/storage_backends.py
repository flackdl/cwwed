import os
import boto3
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class S3ObjectStorage(S3Boto3Storage):
    """
    AWS S3 Storage backend
    """

    def __init__(self, *args, **kwargs):
        self.location = self._get_location()  # ie. "local", "dev", "prod" etc
        self.default_acl = 'private'
        self.access_key = settings.CWWED_ARCHIVES_ACCESS_KEY_ID
        self.secret_key = settings.CWWED_ARCHIVES_SECRET_ACCESS_KEY
        self.bucket_name = settings.AWS_ARCHIVE_BUCKET_NAME
        self.custom_domain = '%s.s3.amazonaws.com' % settings.AWS_ARCHIVE_BUCKET_NAME
        self.auto_create_bucket = True

        super().__init__(*args, **kwargs)

    @staticmethod
    def _get_location():
        """
        Defines a "prefix" path in storage.  Empty if we're deploying to production
        """
        if settings.DEPLOY_STAGE == settings.DEPLOY_STAGE_PROD:
            return ''
        return settings.DEPLOY_STAGE

    def copy_within_storage(self, source: str, destination: str):
        """
        Copies an S3 object to another location within the same bucket
        """

        # delete any existing version if it exists
        if self.exists(destination):
            self.delete(destination)

        # create absolute references to account for the default_storage "location" (prefix)
        source_absolute = self.path(source)
        destination_absolute = self.path(destination)

        # create s3 client
        s3 = boto3.resource(
            's3',
            aws_access_key_id=settings.CWWED_ARCHIVES_ACCESS_KEY_ID,
            aws_secret_access_key=settings.CWWED_ARCHIVES_SECRET_ACCESS_KEY,
        )
        copy_source = {
            'Bucket': settings.AWS_ARCHIVE_BUCKET_NAME,
            'Key': source_absolute,
        }
        s3.meta.client.copy(copy_source, settings.AWS_ARCHIVE_BUCKET_NAME, destination_absolute)

    def path(self, path):
        """
        Include the default_storage "location" (prefix)
        """
        return os.path.join(self.location, path)

    def storage_url(self, path):
        return os.path.join(
            's3://',
            self.bucket_name,
            self.location,
            path,
        )


class S3StaticStorage(S3Boto3Storage):
    """
    AWS S3 Storage backend for static assets
    """

    def __init__(self, *args, **kwargs):
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        self.custom_domain = '%s.s3.amazonaws.com' % settings.AWS_STORAGE_BUCKET_NAME
        self.auto_create_bucket = True
        self.file_overwrite = False
        self.gzip = True

        super().__init__(*args, **kwargs)
