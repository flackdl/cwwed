import os
import boto3
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage


class LocalFileSystemStorage(FileSystemStorage):
    """
    Thin wrapper around the default `FileSystemStorage` to provide a "copy" method
    """

    def copy(self, source: str, destination: str):
        """
        Copies source to destination in local storage
        """
        # delete any existing version if it exists
        if self.exists(destination):
            self.delete(destination)

        with self.open(source, 'rb') as s:
            with self.open(destination, 'wb') as d:
                for chunk in s.chunks():
                    d.write(chunk)


class ObjectStorage(S3Boto3Storage):
    """
    AWS S3 Storage backend
    """

    def __init__(self, *args, **kwargs):
        self.default_acl = 'private'
        self.access_key = settings.CWWED_ARCHIVES_ACCESS_KEY_ID
        self.secret_key = settings.CWWED_ARCHIVES_SECRET_ACCESS_KEY
        self.bucket_name = settings.AWS_ARCHIVE_BUCKET_NAME
        self.custom_domain = '%s.s3.amazonaws.com' % settings.AWS_ARCHIVE_BUCKET_NAME
        self.auto_create_bucket = True

        super().__init__(*args, **kwargs)

    def copy(self, source: str, destination: str):
        """
        Copies an S3 object to another location withing the same bucket
        """
        # delete any existing version if it exists
        if self.exists(destination):
            self.delete(destination)

        # create s3 client
        s3 = boto3.resource(
            's3',
            aws_access_key_id=settings.CWWED_ARCHIVES_ACCESS_KEY_ID,
            aws_secret_access_key=settings.CWWED_ARCHIVES_SECRET_ACCESS_KEY,
        )
        copy_source = {
            'Bucket': settings.AWS_ARCHIVE_BUCKET_NAME,
            'Key': source,
        }
        s3.meta.client.copy(copy_source, settings.AWS_ARCHIVE_BUCKET_NAME, destination)


class StaticStorage(S3Boto3Storage):
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
