import json
import os
import shutil
import pytz
import tarfile
import requests
import xarray as xr
import boto3
from botocore.client import Config as BotoCoreConfig
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.conf import settings
from django.core.mail import send_mail
from django.db import connection
from django.db.models import CharField
from django.db.models.functions import Cast
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from geopandas import GeoDataFrame
from cwwed.celery import app
from cwwed.storage_backends import S3ObjectStoragePrivate
from named_storms.api.serializers import NSEMSerializer
from named_storms.data.processors import ProcessorData
from named_storms.models import NamedStorm, CoveredDataProvider, CoveredData, NamedStormCoveredDataLog, NsemPsa, NsemPsaUserExport, NsemPsaData, NsemPsaVariable
from named_storms.utils import (
    processor_class, named_storm_covered_data_archive_path, copy_path_to_default_storage, named_storm_nsem_version_path,
    get_superuser_emails, named_storm_nsem_psa_version_path, root_data_path,
    create_directory)


TASK_ARGS = dict(
    autoretry_for=(Exception,),
    default_retry_delay=5,
    max_retries=10,
)


@app.task(**TASK_ARGS)
def fetch_url_task(url, verify=True, write_to_path=None):
    """
    :param url: URL to fetch
    :param verify: whether to verify ssl
    :param write_to_path: path to store the output vs returning it
    """
    stream = write_to_path is not None
    response = requests.get(url, verify=verify, timeout=10, stream=stream)
    response.raise_for_status()

    # save content
    if write_to_path is not None:
        with open(write_to_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
        return None

    # return content
    return response.content.decode()  # must return bytes for serialization


@app.task(**TASK_ARGS)
def process_dataset_task(data: list):
    """
    Run the dataset processor
    """
    processor_data = ProcessorData(*data)
    named_storm = get_object_or_404(NamedStorm, pk=processor_data.named_storm_id)
    provider = get_object_or_404(CoveredDataProvider, pk=processor_data.provider_id)
    processor_cls = processor_class(provider)
    processor = processor_cls(
        named_storm=named_storm,
        provider=provider,
        url=processor_data.url,
        label=processor_data.label,
        group=processor_data.group,
        **processor_data.kwargs,  # include any extra kwargs
    )
    processor.fetch()
    return processor.to_dict()


@app.task(**TASK_ARGS)
def archive_named_storm_covered_data_task(named_storm_id, covered_data_id, log_id):
    """
    Archives a covered data collection and sends it to object storage
    :param named_storm_id: id for a NamedStorm record
    :param covered_data_id: id for a CoveredData record
    :param log_id: id for a NamedStormCoveredDataLog
    """
    named_storm = get_object_or_404(NamedStorm, pk=named_storm_id)
    covered_data = get_object_or_404(CoveredData, pk=covered_data_id)
    log = get_object_or_404(NamedStormCoveredDataLog, pk=log_id)

    archive_path = named_storm_covered_data_archive_path(named_storm, covered_data)
    tar_path = '{}.{}'.format(
        os.path.join(os.path.dirname(archive_path), os.path.basename(archive_path)),  # guarantees no trailing slash
        settings.CWWED_ARCHIVE_EXTENSION,
    )

    # create tar in local storage
    tar = tarfile.open(tar_path, mode=settings.CWWED_NSEM_ARCHIVE_WRITE_MODE)
    tar.add(archive_path, arcname=os.path.basename(archive_path))
    tar.close()

    storage_path = os.path.join(
        settings.CWWED_COVERED_ARCHIVE_DIR_NAME,
        named_storm.name,
        os.path.basename(tar_path),
    )

    # copy tar to object storage
    snapshot_path = copy_path_to_default_storage(tar_path, storage_path)

    # remove local tar
    os.remove(tar_path)

    # update the log with the saved snapshot
    log.snapshot = snapshot_path
    log.save()

    return log.snapshot


@app.task(**TASK_ARGS)
def archive_nsem_covered_data_task(nsem_id):
    """
    - Copies all covered data archives to a versioned NSEM location in object storage so users can download them directly
    :param nsem_id: id of NsemPsa record
    """

    # retrieve all the successful covered data by querying the logs
    # exclude any logs where the snapshot archive hasn't been created yet
    # sort by date descending and retrieve unique results
    nsem = get_object_or_404(NsemPsa, pk=int(nsem_id))
    logs = nsem.named_storm.namedstormcovereddatalog_set.filter(success=True).exclude(snapshot='').order_by('-date')
    if not logs.exists():
        return None
    logs_to_archive = []
    for log in logs:
        if log.covered_data.name not in [l.covered_data.name for l in logs_to_archive]:
            logs_to_archive.append(log)

    storage_path = os.path.join(
        settings.CWWED_NSEM_DIR_NAME,
        nsem.named_storm.name,
        'v{}'.format(nsem.id),
        settings.CWWED_COVERED_DATA_DIR_NAME,
    )

    for log in logs_to_archive:
        src_path = log.snapshot
        dest_path = os.path.join(storage_path, os.path.basename(src_path))
        # copy snapshot to versioned nsem location in default storage
        S3ObjectStoragePrivate().copy_within_storage(src_path, dest_path)

    nsem.covered_data_logs.set(logs_to_archive)  # many to many field
    nsem.covered_data_snapshot = storage_path
    nsem.save()

    return NSEMSerializer(instance=nsem).data


@app.task(**TASK_ARGS)
def extract_nsem_covered_data_task(nsem_data: dict):
    """
    Downloads and extracts nsem covered data into file storage
    :param nsem_data: dictionary of NsemPsa record
    """
    nsem = get_object_or_404(NsemPsa, pk=nsem_data['id'])
    file_system_path = os.path.join(
        named_storm_nsem_version_path(nsem),
        settings.CWWED_COVERED_DATA_DIR_NAME,
    )
    # download all the archives
    storage = S3ObjectStoragePrivate()
    storage.download_directory(
        storage.path(nsem.covered_data_snapshot), file_system_path)

    # extract the archives
    for file in os.listdir(file_system_path):
        if file.endswith(settings.CWWED_ARCHIVE_EXTENSION):
            file_path = os.path.join(file_system_path, file)
            tar = tarfile.open(file_path, settings.CWWED_NSEM_ARCHIVE_READ_MODE)
            tar.extractall(file_system_path)
            tar.close()
            # remove the original archive now that it's extracted
            os.remove(file_path)
    return NSEMSerializer(instance=nsem).data


class ExtractNSEMTaskBase(app.Task):

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        On Failure, this posts to slack and emails the "nsem" user (and super users).
        The first value in `args` is expected to be the nsem_id that failed to extract the uploaded PSA.
        """
        super().on_failure(exc, task_id, args, kwargs, einfo)

        # the first arg should be the nsem
        if args:
            nsem = NsemPsa.objects.filter(pk=args[0])
            if nsem.exists():
                nsem = nsem.get()
                nsem_user = User.objects.get(username=settings.CWWED_NSEM_USER)
                # include the "nsem" user and all super users
                recipients = get_superuser_emails()
                if nsem_user.email:
                    recipients.append(nsem_user.email)
                send_mail(
                    subject='Failed extracting PSA v{}'.format(nsem.id),
                    message=str(exc),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=recipients,
                )


EXTRACT_NSEM_TASK_ARGS = TASK_ARGS.copy()  # type: dict
EXTRACT_NSEM_TASK_ARGS.update({
    'base': ExtractNSEMTaskBase,
})


@app.task(**EXTRACT_NSEM_TASK_ARGS)
def extract_nsem_model_output_task(nsem_id):
    """
    Downloads the model product output from object storage and puts it in file storage
    """

    nsem = get_object_or_404(NsemPsa, pk=int(nsem_id))
    uploaded_file_path = nsem.model_output_snapshot
    storage = S3ObjectStoragePrivate()

    # verify this instance needs it's model output to be extracted (don't raise an exception to avoid this task retrying)
    if nsem.model_output_snapshot_extracted:
        return None
    elif not uploaded_file_path:
        raise Http404("Missing model output snapshot")
    # verify the uploaded output exists in storage
    elif not storage.exists(uploaded_file_path):
        raise Http404("{} doesn't exist in storage".format(uploaded_file_path))

    storage_path = os.path.join(
        settings.CWWED_NSEM_DIR_NAME,
        nsem.named_storm.name,
        'v{}'.format(nsem.id),
        settings.CWWED_NSEM_PSA_DIR_NAME,
        os.path.basename(uploaded_file_path),
    )

    # copy from "upload" directory to the versioned path
    storage.copy_within_storage(uploaded_file_path, storage_path)

    file_system_path = os.path.join(
        named_storm_nsem_version_path(nsem),
        settings.CWWED_NSEM_PSA_DIR_NAME,
        os.path.basename(uploaded_file_path),
    )

    # download to the file system
    storage.download_file(storage.path(storage_path), file_system_path)

    # extract the tgz
    tar = tarfile.open(file_system_path, settings.CWWED_NSEM_ARCHIVE_READ_MODE)
    tar.extractall(os.path.dirname(file_system_path))
    tar.close()

    # recursively update the permissions for all extracted directories and files
    for root, dirs, files in os.walk(os.path.dirname(file_system_path)):
        # using octal literal notation for chmod
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o755)
        for f in files:
            os.chmod(os.path.join(root, f), 0o644)

    # remove the tgz now that we've extracted everything
    os.remove(file_system_path)

    # update output path to the copied path, flag success and set the date returned
    nsem.model_output_snapshot = storage_path
    nsem.model_output_snapshot_extracted = True
    nsem.date_returned = datetime.utcnow()
    nsem.save()

    # delete the original/uploaded copy
    storage.delete(uploaded_file_path)

    return storage.url(storage_path)


@app.task(**TASK_ARGS)
def email_nsem_covered_data_complete_task(nsem_data: dict, base_url: str):
    """
    Email the "nsem" user indicating the Covered Data for a particular post storm assessment is complete and ready for download.
    :param nsem_data serialized NsemPsa instance
    :param base_url the scheme & domain that this request arrived
    """
    nsem = get_object_or_404(NsemPsa, pk=nsem_data['id'])
    nsem_user = User.objects.get(username=settings.CWWED_NSEM_USER)

    body = """
        {}
        
        {}
        """.format(
        # link to api endpoint for this nsem instance
        '{}{}'.format(base_url, reverse('nsem-detail', args=[nsem.id])),
        # raw json dump
        json.dumps(nsem_data, indent=2),
    )

    # include the "nsem" user and all super users
    recipients = get_superuser_emails()
    if nsem_user.email:
        recipients.append(nsem_user.email)

    send_mail(
        subject='Covered Data is ready for download (PSA v{})'.format(nsem.id),
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
    )
    return nsem_data


@app.task(**TASK_ARGS)
def create_psa_user_export_task(nsem_psa_user_export_id: int):
    # TODO - this is a proof of concept and is only working with the water dataset
    #        it assumes gridded with specific variables
    nsem_psa_user_export = get_object_or_404(NsemPsaUserExport, id=nsem_psa_user_export_id)
    date_expires = pytz.utc.localize(datetime.utcnow()) + timedelta(days=settings.CWWED_PSA_USER_DATA_EXPORT_DAYS)

    psa_path = named_storm_nsem_psa_version_path(nsem_psa_user_export.nsem)
    tmp_user_export_path = os.path.join(
        root_data_path(),
        settings.CWWED_NSEM_TMP_USER_EXPORT_DIR_NAME,
        str(nsem_psa_user_export.id),
    )
    tar_path = os.path.join(
        tmp_user_export_path,
        '{}.tgz'.format(nsem_psa_user_export.nsem.named_storm),
    )

    # create temporary directory
    create_directory(tmp_user_export_path)

    # netcdf/csv - extract low level data from netcdf files
    if nsem_psa_user_export.format in [NsemPsaUserExport.FORMAT_NETCDF, NsemPsaUserExport.FORMAT_CSV]:

        for ds_file in os.listdir(psa_path):

            # only processing netcdf files
            if not ds_file.endswith('.nc'):
                continue

            ds_file_path = os.path.join(psa_path, ds_file)

            # open dataset
            ds = xr.open_dataset(ds_file_path)

            # subset using user-defined bounding box
            ds = ds.where(
                (ds.lat >= nsem_psa_user_export.bbox.extent[1]) &
                (ds.lon >= nsem_psa_user_export.bbox.extent[0]) &
                (ds.lat <= nsem_psa_user_export.bbox.extent[3]) &
                (ds.lon <= nsem_psa_user_export.bbox.extent[2]), drop=True)

            if nsem_psa_user_export.format == NsemPsaUserExport.FORMAT_NETCDF:
                # use xarray to create the netcdf export
                ds.to_netcdf(os.path.join(tmp_user_export_path, ds_file))
            elif nsem_psa_user_export.format == NsemPsaUserExport.FORMAT_CSV:
                pass

    # shapefile - extract pre-processed contour data from db
    elif nsem_psa_user_export.format == NsemPsaUserExport.FORMAT_SHAPEFILE:
        # generate shapefiles for all polygon variables
        for psa_geom_variable in nsem_psa_user_export.nsem.nsempsavariable_set.filter(geo_type=NsemPsaVariable.GEO_TYPE_POLYGON):

            #
            # generate sql query to send to geopanda's GeoDataFrame to create a shapefile
            #

            # NOTE: we have to fetch all the ids of the actual data up front because we need to send the raw query to
            # GeoPandas, but django doesn't produce valid sql due to it not quoting params (specifically dates), so this
            # technique is a workaround

            # fetch the ids of the data we want
            kwargs = {
                'nsem_psa_variable__id': psa_geom_variable.id,
            }
            # only include date if it's a time series variable
            if psa_geom_variable.data_type == NsemPsaVariable.DATA_TYPE_TIME_SERIES:
                kwargs['date'] = nsem_psa_user_export.date_filter
            qs = NsemPsaData.objects.filter(**kwargs)
            data_ids = [r['id'] for r in qs.values('id')]

            # generate raw sql query to send to geopanda's GeoDataFrame
            qs = NsemPsaData.objects.annotate(geom=Cast('geo', CharField()))
            qs = qs.filter(id__in=data_ids)
            qs = qs.values('geom', 'value')
            gdf = GeoDataFrame.from_postgis(str(qs.query), connection, geom_col='geom')
            gdf.to_file(os.path.join(tmp_user_export_path, '{}.shp'.format(psa_geom_variable.name)))

    # create tar in local storage
    tar = tarfile.open(tar_path, mode=settings.CWWED_NSEM_ARCHIVE_WRITE_MODE)
    tar.add(tmp_user_export_path, arcname=str(nsem_psa_user_export.nsem.named_storm))
    tar.close()

    #
    # create pre-signed url and upload to S3
    # https://aws.amazon.com/premiumsupport/knowledge-center/presigned-url-s3-bucket-expiration/
    #

    # get the service client with sigv4 configured
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.CWWED_ARCHIVES_ACCESS_KEY_ID,
        aws_secret_access_key=settings.CWWED_ARCHIVES_SECRET_ACCESS_KEY,
        config=BotoCoreConfig(signature_version='s3v4'))

    # user export key name (using the export_id enforces uniqueness)
    key_name = '{dir}/{storm_name}-{export_id}.{extension}'.format(
        dir=settings.CWWED_NSEM_S3_USER_EXPORT_DIR_NAME,
        export_id=nsem_psa_user_export.id,
        storm_name=nsem_psa_user_export.nsem.named_storm,
        extension=settings.CWWED_ARCHIVE_EXTENSION,
    )

    # handle staging base paths (i.e "local", "dev", "test")
    s3_base_location = S3ObjectStoragePrivate().location
    if s3_base_location:
        key_name = '{}/{}'.format(s3_base_location, key_name)

    # generate the pre-signed URL
    presigned_url = s3_client.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': settings.AWS_ARCHIVE_BUCKET_NAME,
            'Key': key_name,
        },
        ExpiresIn=settings.CWWED_PSA_USER_DATA_EXPORT_DAYS * 24 * 60 * 60,
    )

    # upload tar to s3 object with expiration
    s3_resource = boto3.resource(
        's3',
        aws_access_key_id=settings.CWWED_ARCHIVES_ACCESS_KEY_ID,
        aws_secret_access_key=settings.CWWED_ARCHIVES_SECRET_ACCESS_KEY,
    )
    s3_resource.Bucket(settings.AWS_ARCHIVE_BUCKET_NAME).put_object(
        Key=key_name,
        Body=open(tar_path, 'rb'),
        Expires=date_expires,
    )

    # remove temporary directory
    shutil.rmtree(tmp_user_export_path)

    nsem_psa_user_export.date_expires = date_expires
    nsem_psa_user_export.date_completed = pytz.utc.localize(datetime.utcnow())
    nsem_psa_user_export.url = presigned_url
    nsem_psa_user_export.save()

    return nsem_psa_user_export.id


@app.task(**TASK_ARGS)
def email_psa_user_export_task(nsem_psa_user_export_id: int):
    nsem_psa_user_export = get_object_or_404(NsemPsaUserExport, id=nsem_psa_user_export_id)

    body = """
        Storm: {storm}
        Format: {format}
        Expires: {expires}
        Bounding Box: {bbox}
        Download Link: {url}
    """.format(
        storm=nsem_psa_user_export.nsem.named_storm,
        bbox=nsem_psa_user_export.bbox.wkt,
        format=nsem_psa_user_export.format,
        expires=nsem_psa_user_export.date_expires.isoformat(),
        url=nsem_psa_user_export.url,
    )

    # email the user
    send_mail(
        subject='Post Storm Assessment export: {}'.format(
            nsem_psa_user_export.nsem.named_storm),
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[nsem_psa_user_export.user.email],
    )
