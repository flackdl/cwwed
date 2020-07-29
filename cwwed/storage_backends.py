import os
import boto3
import logging
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage
from named_storms.utils import create_directory

logger = logging.getLogger('cwwed')


class S3ObjectStorage(S3Boto3Storage):
    """
    AWS S3 Storage backend
    """

    def __init__(self, *args, **kwargs):
        self.location = 'Coastal Act'
        self.default_acl = 'public-read'
        self.access_key = settings.CWWED_ARCHIVES_ACCESS_KEY_ID
        self.secret_key = settings.CWWED_ARCHIVES_SECRET_ACCESS_KEY
        self.bucket_name = settings.AWS_ARCHIVE_BUCKET_NAME
        self.custom_domain = '%s.s3.amazonaws.com' % settings.AWS_ARCHIVE_BUCKET_NAME
        self.auto_create_bucket = True

        super().__init__(*args, **kwargs)

    def _get_s3_resource(self):
        return boto3.resource(
            's3',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )


class S3ObjectStoragePrivate(S3ObjectStorage):

    def __init__(self, *args, force_root_location=False, **kwargs):
        super().__init__(*args, **kwargs)
        if force_root_location:
            self.location = ''
        else:
            self.location = self._get_location()  # ie. "local", "dev", "alpha" or "" when in production
        self.default_acl = 'private'

    @staticmethod
    def _get_location():
        """
        Defines a "prefix" path in storage.  Empty if we're deploying to production
        """
        if settings.DEPLOY_STAGE == settings.DEPLOY_STAGE_PROD:
            return ''
        return settings.DEPLOY_STAGE

    def download_directory(self, obj_directory_path, file_system_path):
        # create the s3 instance
        s3 = self._get_s3_resource()
        s3_bucket = s3.Bucket(self.bucket_name)

        # create directory output directory on file system
        create_directory(file_system_path)

        # download each object that matches the `obj_directory_path` prefix
        for obj in s3_bucket.objects.all():
            if obj.key.startswith(obj_directory_path):
                self.download_file(obj.key, os.path.join(file_system_path, os.path.basename(obj.key)))

    def download_file(self, obj_path, file_system_path):
        # create directory then download to file system path
        create_directory(os.path.dirname(file_system_path))
        s3 = self._get_s3_resource()
        s3.Bucket(self.bucket_name).download_file(obj_path, file_system_path)

    def copy_within_storage(self, source: str, destination: str):
        """
        Copies an S3 object to another location within the same bucket
        """

        if not self.exists(source):
            logger.warning('skipping source that does not exist: {}'.format(source))
            return

        # delete any existing version if it exists
        if self.exists(destination):
            self.delete(destination)

        # create absolute references to account for the object storage "location" (prefix)
        source_absolute = self.path(source)
        destination_absolute = self.path(destination)

        s3 = self._get_s3_resource()
        copy_source = {
            'Bucket': settings.AWS_ARCHIVE_BUCKET_NAME,
            'Key': source_absolute,
        }
        s3.meta.client.copy(copy_source, self.bucket_name, destination_absolute)

    def path(self, path):
        """
        Include the storage "location" (prefix), i.e "local", "dev", "test" etc.  Will be empty when in production
        """
        return os.path.join(self.location, path)

    def storage_url(self, path):
        return os.path.join(
            's3://',
            self.bucket_name,
            self.location,
            path,
        )
