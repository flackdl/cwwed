import os
import shutil
import pytz
import tarfile
import requests
import xarray as xr
import boto3
import numpy as np
import pandas as pd
from celery.utils.log import get_task_logger
from cfchecker import cfchecks
from botocore.client import Config as BotoCoreConfig
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib.gis.db.models import Collect, GeometryField
from django.contrib.gis.db.models.functions import Intersection, MakeValid, AsKML
from django.core.mail import send_mail
from django.db import connection
from django.db.models import CharField
from django.db.models.functions import Cast
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from geopandas import GeoDataFrame
from cwwed.celery import app
from cwwed.storage_backends import S3ObjectStoragePrivate
from named_storms.data.processors import ProcessorData
from named_storms.models import (
    NamedStorm, CoveredDataProvider, CoveredData, NamedStormCoveredDataLog, NsemPsa, NsemPsaUserExport,
    NsemPsaData, NsemPsaVariable, NamedStormCoveredDataSnapshot)
from named_storms.utils import (
    processor_class, copy_path_to_default_storage, get_superuser_emails,
    named_storm_nsem_version_path, root_data_path, create_directory,
    get_geojson_feature_collection_from_psa_qs, named_storm_path,
    named_storm_covered_data_current_path)

# celery logger
logger = get_task_logger(__name__)


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

    archive_path = named_storm_covered_data_current_path(named_storm, covered_data)
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
    log.date_completed = pytz.utc.localize(datetime.utcnow())
    log.save()

    return log.snapshot


@app.task(**TASK_ARGS)
def create_named_storm_covered_data_snapshot_task(named_storm_covered_data_snapshot_id):
    """
    - Creates a snapshot of a storm's covered data and archives in object storage
    """

    # retrieve all the successful covered data by querying the logs
    # sort by date descending and retrieve unique results
    covered_data_snapshot = get_object_or_404(NamedStormCoveredDataSnapshot, pk=int(named_storm_covered_data_snapshot_id))
    logs = covered_data_snapshot.named_storm.namedstormcovereddatalog_set.filter(success=True).exclude(date_completed__isnull=True).order_by('-date_completed')

    if not logs.exists():
        return None
    logs_to_archive = []
    for log in logs:
        if log.covered_data.name not in [l.covered_data.name for l in logs_to_archive]:
            logs_to_archive.append(log)

    storage_path = os.path.join(
        settings.CWWED_NSEM_DIR_NAME,
        covered_data_snapshot.named_storm.name,
        settings.CWWED_COVERED_DATA_SNAPSHOTS_DIR_NAME,
        str(covered_data_snapshot.id),
    )

    for log in logs_to_archive:
        src_path = log.snapshot
        dest_path = os.path.join(storage_path, os.path.basename(src_path))
        # copy snapshot to the storm's snapshot directory in default storage
        S3ObjectStoragePrivate().copy_within_storage(src_path, dest_path)

    covered_data_snapshot.path = storage_path
    covered_data_snapshot.date_completed = pytz.utc.localize(datetime.utcnow())
    covered_data_snapshot.covered_data_logs.set(logs_to_archive)
    covered_data_snapshot.save()

    return covered_data_snapshot.id


@app.task(**TASK_ARGS)
def extract_named_storm_covered_data_snapshot_task(named_storm_covered_data_snapshot_id):
    """
    Downloads and extracts a named storm covered data snapshot into file storage
    """
    named_storm_covered_data_snapshot = get_object_or_404(NamedStormCoveredDataSnapshot, pk=named_storm_covered_data_snapshot_id)

    file_system_path = os.path.join(
        named_storm_path(named_storm_covered_data_snapshot.named_storm),
        settings.CWWED_COVERED_DATA_SNAPSHOTS_DIR_NAME,
        str(named_storm_covered_data_snapshot.id),
    )

    # download all the archives
    storage = S3ObjectStoragePrivate()
    storage.download_directory(
        storage.path(named_storm_covered_data_snapshot.path), file_system_path)

    # extract the archives
    for file in os.listdir(file_system_path):
        if file.endswith(settings.CWWED_ARCHIVE_EXTENSION):
            file_path = os.path.join(file_system_path, file)
            tar = tarfile.open(file_path, settings.CWWED_NSEM_ARCHIVE_READ_MODE)
            tar.extractall(file_system_path)
            tar.close()
            # remove the original archive now that it's extracted
            os.remove(file_path)

    return named_storm_covered_data_snapshot.id


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
                    subject='Failed extracting PSA {}'.format(nsem.id),
                    message=str(exc),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=recipients,
                )


EXTRACT_NSEM_TASK_ARGS = TASK_ARGS.copy()  # type: dict
EXTRACT_NSEM_TASK_ARGS.update({
    'base': ExtractNSEMTaskBase,
})


@app.task(**EXTRACT_NSEM_TASK_ARGS)
def extract_nsem_psa_task(nsem_id):
    """
    Downloads the model product output from object storage and puts it in file storage
    """

    nsem = get_object_or_404(NsemPsa, pk=int(nsem_id))
    uploaded_file_path = nsem.path
    storage = S3ObjectStoragePrivate()

    # remove any prefixed "location" from the object storage instance (i.e , "local", "dev", "test")
    location_prefix = '{}/'.format(storage.location)
    if uploaded_file_path.startswith(location_prefix):
        uploaded_file_path = uploaded_file_path.replace(location_prefix, '')

    # verify this instance needs it's model output to be extracted (don't raise an exception to avoid this task retrying)
    if nsem.extracted:
        return None
    elif not uploaded_file_path:
        raise Http404("Missing model output")
    # verify the uploaded output exists in storage
    elif not storage.exists(uploaded_file_path):
        raise Http404("{} doesn't exist in storage".format(uploaded_file_path))

    storage_path = os.path.join(
        settings.CWWED_NSEM_DIR_NAME,
        nsem.named_storm.name,
        str(nsem.id),
        os.path.basename(uploaded_file_path),
    )

    # copy from "upload" directory to the versioned path
    storage.copy_within_storage(uploaded_file_path, storage_path)

    file_system_path = os.path.join(
        named_storm_nsem_version_path(nsem),
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

    # update output path to the copied path and flag success
    nsem.path = storage_path
    nsem.extracted = True
    nsem.save()

    # delete the original/uploaded copy
    storage.delete(uploaded_file_path)

    return storage.url(storage_path)


@app.task(**TASK_ARGS)
def email_nsem_user_covered_data_complete_task(named_storm_covered_data_snapshot_id: int):
    """
    Email the "nsem" user indicating the Covered Data for a particular storm is complete and ready for download.
    """
    named_storm_covered_data_snapshot = get_object_or_404(NamedStormCoveredDataSnapshot, pk=named_storm_covered_data_snapshot_id)
    nsem_user = User.objects.get(username=settings.CWWED_NSEM_USER)

    body = """
        Covered Data is ready to download for {}.
        
        COVERED DATA URL: {}
        """.format(
        named_storm_covered_data_snapshot.named_storm,
        named_storm_covered_data_snapshot.get_covered_data_storage_url(),
    )

    html_body = render_to_string(
        'email_nsem_user_covered_data_complete.html',
        context={
            "named_storm_covered_data_snapshot": named_storm_covered_data_snapshot,
        })

    # include the "nsem" user and all super users
    recipients = get_superuser_emails()
    if nsem_user.email:
        recipients.append(nsem_user.email)

    send_mail(
        subject='Covered Data is ready to download for {}'.format(named_storm_covered_data_snapshot.named_storm),
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        html_message=html_body,
    )

    return named_storm_covered_data_snapshot.id


@app.task(**TASK_ARGS)
def email_psa_validated_task(nsem_psa_id):
    """
    Email the "nsem" user indicating whether the PSA has been validated or not
    """
    nsem_psa = get_object_or_404(NsemPsa, pk=nsem_psa_id)
    nsem_user = User.objects.get(username=settings.CWWED_NSEM_USER)
    nsem_psa_api_url = "{}://{}:{}{}".format(
        settings.CWWED_SCHEME, settings.CWWED_HOST, settings.CWWED_PORT, reverse('nsempsa-detail', args=[nsem_psa.id]))

    body = """
        {message}
        
        API: {api_url}
        """.format(
        message='PSA was validated' if nsem_psa.validated else 'PSA was rejected: {}'.format(nsem_psa.validation_exceptions),
        api_url=nsem_psa_api_url,
    )

    html_body = render_to_string(
        'email_psa_validated.html',
        context={
            "nsem_psa": nsem_psa,
            "nsem_psa_api_url": nsem_psa_api_url,
        })

    # include the "nsem" user and all super users
    recipients = get_superuser_emails()
    if nsem_user.email:
        recipients.append(nsem_user.email)

    send_mail(
        subject='PSA {validated} ({psa_id})'.format(
            validated='validated' if nsem_psa.validated else 'rejected', psa_id=nsem_psa.id),
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        html_message=html_body,
    )
    return nsem_psa.id


@app.task(**EXTRACT_NSEM_TASK_ARGS)
def validate_nsem_psa_task(nsem_id):
    """
    Validates the PSA model product output from file storage with the following:
    - cf conventions - http://cfconventions.org/
    - expected coordinates
    - proper time dimension & timezone (xarray throws ValueError if it can't decode it automatically)
    - duplicate dimension & scalar values (xarray throws ValueError if encountered)
    - netcdf only
    - NaNs
    """

    valid_files = []
    required_coords = {'time', 'lat', 'lon'}
    required_wind_variables = {'wspd10m', 'wdir10m'}
    exceptions = {
        'global': [],
        'files': {},
    }

    nsem_psa = get_object_or_404(NsemPsa, pk=int(nsem_id))

    # clear any previous validations
    nsem_psa.validation_exceptions = {}
    nsem_psa.validated_files = []
    nsem_psa.date_validation = None

    psa_path = named_storm_nsem_version_path(nsem_psa)
    for file_name in os.listdir(psa_path):
        if file_name.endswith('.nc'):
            file_path = os.path.join(psa_path, file_name)
            file_exceptions = []
            variable_exceptions = {}
            try:
                ds = xr.open_dataset(file_path)
            except (ValueError, OSError) as e:
                file_exceptions.append(str(e))
            else:

                # cf conventions
                cf_check = cfchecks.CFChecker()
                cf_check.checker(file_path)
                file_exceptions += cf_check.results['global']['FATAL']
                file_exceptions += cf_check.results['global']['ERROR']
                for variable, result in cf_check.results['variables'].items():
                    if result['FATAL'] or result['ERROR']:
                        variable_exceptions[variable] = result['FATAL'] + result['ERROR']

                # coordinates
                if not required_coords.issubset(list(ds.coords)):
                    file_exceptions.append('Missing required coordinates: {}'.format(required_coords))

                # TODO - validate the following:
                # water & wind dataset exists
                # time-series: all files should have the same temporal frequency
                # structured

                # nans
                # TODO - only validating NaNs with wind dataset because the water dataset isn't structured yet and has Nans
                if required_wind_variables.issubset(list(ds.variables)):
                    for variable in required_wind_variables:
                        if ds[variable].isnull().any():
                            if variable not in variable_exceptions:
                                variable_exceptions[variable] = []
                            variable_exceptions[variable].append('has null values')

            if file_exceptions or variable_exceptions:
                e = {'file': file_exceptions, 'variables': variable_exceptions}
                exceptions['files'][file_name] = e
            else:
                valid_files.append(file_name)

    if not valid_files:
        exceptions['global'] = ['no valid files found']

    # TODO - XXX must not reset anything since we don't have to re-snapshot the CD
    #        XXX just have them create a new PSA

    # error
    if exceptions['global'] or exceptions['files']:
        nsem_psa.validation_exceptions = exceptions

        # delete the psa from object storage
        storage = S3ObjectStoragePrivate()
        storage.delete(nsem_psa.path)

        # reset the psa instance so more attempts can be made
        nsem_psa.path = ''
        nsem_psa.extracted = False

    # success
    else:
        nsem_psa.validated = True
        nsem_psa.validated_files = valid_files
    nsem_psa.date_validation = datetime.utcnow().replace(tzinfo=pytz.utc)
    nsem_psa.save()


@app.task(**TASK_ARGS)
def create_psa_user_export_task(nsem_psa_user_export_id: int):

    # TODO - this is a proof of concept while we wait on a finalized psa structure

    nsem_psa_user_export = get_object_or_404(NsemPsaUserExport, id=nsem_psa_user_export_id)

    date_expires = pytz.utc.localize(datetime.utcnow()) + timedelta(days=settings.CWWED_PSA_USER_DATA_EXPORT_DAYS)

    psa_path = named_storm_nsem_version_path(nsem_psa_user_export.nsem)
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
                (ds.lon >= nsem_psa_user_export.bbox.extent[0]) &  # xmin
                (ds.lat >= nsem_psa_user_export.bbox.extent[1]) &  # ymin
                (ds.lon <= nsem_psa_user_export.bbox.extent[2]) &  # xmax
                (ds.lat <= nsem_psa_user_export.bbox.extent[3]),   # ymax
                drop=True)

            # skip dataset if there is missing data on any dimensions (ie. bounding box could have been too small)
            if not all([len(ds[d]) for d in list(ds.dims)]):
                continue

            # netcdf
            if nsem_psa_user_export.format == NsemPsaUserExport.FORMAT_NETCDF:
                # use xarray to create the netcdf export
                ds.to_netcdf(os.path.join(tmp_user_export_path, ds_file))

            # csv
            elif nsem_psa_user_export.format == NsemPsaUserExport.FORMAT_CSV:

                # verify this dataset has the export date requested
                if not ds.time.isin([np.datetime64(nsem_psa_user_export.date_filter)]).any():
                    continue

                # subset by export date filter
                ds = ds.sel(time=np.datetime64(nsem_psa_user_export.date_filter))

                # TODO - we're only including the following variables while we're waiting on explicit instruction
                wind_variables = ['wspd10m', 'wdir10m']
                water_variables = ['water_level', 'wave_height']

                # test if this is the water product
                if set(water_variables).intersection(ds.variables.keys()):
                    variables = water_variables
                elif set(wind_variables).intersection(ds.variables.keys()):
                    variables = wind_variables
                else:  # none found, skip this dataset
                    logger.warning('No expected data fround in {}'.format(ds_file))
                    continue

                # create pandas DataFrame which makes a csv conversion very simple
                df_out = pd.DataFrame()

                # insert a new column for each variable to df_out
                for i, variable in enumerate(variables):
                    df = ds[variable].to_dataframe()

                    # initialize df_out DataFrame on first iteration
                    if i == 0:
                        df_out = df
                    # insert df Series as a new column
                    else:
                        df_out.insert(len(df_out.columns), variable, df[variable])

                # NOTE: due to the "crooked" shape of the structured grid
                # this is necessary because the above xarray "where" bbox/extent
                # filter is including coords _just_ outside the requested extent with no values present,
                # so this simply guarantees those rows are removed
                df_out = df_out.dropna()

                # write csv
                df_out.to_csv(
                    os.path.join(tmp_user_export_path, '{}.csv'.format(ds_file)), index=False)

    # shapefile - extract pre-processed contour data from db
    elif nsem_psa_user_export.format == NsemPsaUserExport.FORMAT_SHAPEFILE:

        # generate shapefiles for all time-series polygon variables
        for psa_geom_variable in nsem_psa_user_export.nsem.nsempsavariable_set.filter(geo_type=NsemPsaVariable.GEO_TYPE_POLYGON):

            #
            # generate sql query to send to geopanda's GeoDataFrame.from_postgis() to create a shapefile
            #

            # NOTE: we have to fetch all the ids of the actual data up front because we need to send the raw query to
            # GeoPandas, but django doesn't produce valid sql when using QuerySet.query due to it not quoting params (specifically dates),
            # so this technique is a workaround

            # fetch the ids of the psa data for this psa variable and that intersects the export's requested bbox
            kwargs = dict(
                nsem_psa_variable__id=psa_geom_variable.id,
                geo__intersects=nsem_psa_user_export.bbox,
            )

            # only include date if it's a time series variable
            if psa_geom_variable.data_type == NsemPsaVariable.DATA_TYPE_TIME_SERIES:
                kwargs['date'] = nsem_psa_user_export.date_filter

            qs = NsemPsaData.objects.filter(**kwargs)
            data_ids = [r['id'] for r in qs.values('id')]

            # group all intersecting geometries together by value and clip the result using the export's bbox intersection
            # also, it's necessary to finally cast to CharField for GeoPandas
            # NOTE: using ST_MakeValid due to ring self-intersections which ST_Intersection chokes on
            qs = NsemPsaData.objects.filter(id__in=data_ids)
            qs = qs.values('value')
            qs = qs.annotate(
                geom=Cast(Intersection(Collect(MakeValid(Cast('geo', GeometryField()))), nsem_psa_user_export.bbox), CharField()))

            # create GeoDataFrame from query
            gdf = GeoDataFrame.from_postgis(str(qs.query), connection, geom_col='geom')

            # save to temporary user path
            gdf.to_file(os.path.join(tmp_user_export_path, '{}.shp'.format(psa_geom_variable.name)))

    # extract pre-processed geo data from db
    elif nsem_psa_user_export.format in [NsemPsaUserExport.FORMAT_GEOJSON, NsemPsaUserExport.FORMAT_KML]:

        for psa_variable in nsem_psa_user_export.nsem.nsempsavariable_set.all():
            data_kwargs = dict(
                geo__intersects=nsem_psa_user_export.bbox,
            )
            # only include date if it's a time series variable
            if psa_variable.data_type == NsemPsaVariable.DATA_TYPE_TIME_SERIES:
                data_kwargs['date'] = nsem_psa_user_export.date_filter

            # group all intersecting geometries together by variable & value and
            # only return the export's bbox intersection
            # NOTE: using ST_MakeValid due to ring self-intersections which ST_Intersection chokes on
            qs = psa_variable.nsempsadata_set.filter(**data_kwargs)
            qs = qs.values(*['value', 'meta', 'color', 'date', 'nsem_psa_variable__name', 'nsem_psa_variable__units'])
            qs = qs.annotate(geom=Intersection(Collect(MakeValid(Cast('geo', GeometryField()))), nsem_psa_user_export.bbox))

            if nsem_psa_user_export.format == NsemPsaUserExport.FORMAT_KML:
                # annotate with AsKML
                qs = qs.annotate(kml=AsKML('geom'))
                # write kml to file
                with open(os.path.join(tmp_user_export_path, '{}.kml'.format(psa_variable.name)), 'w') as fh:
                    fh.write(render_to_string('psa_export.kml', context={"results": qs, "psa_variable": psa_variable}))
            elif nsem_psa_user_export.format == NsemPsaUserExport.FORMAT_GEOJSON:
                # write geojson to file
                with open(os.path.join(tmp_user_export_path, '{}.json'.format(psa_variable.name)), 'w') as fh:
                    fh.write(get_geojson_feature_collection_from_psa_qs(qs))

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
    with open(tar_path, 'rb') as fh:
        s3_resource.Bucket(settings.AWS_ARCHIVE_BUCKET_NAME).put_object(
            Key=key_name,
            Body=fh,
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

    context = dict(
        storm=nsem_psa_user_export.nsem.named_storm,
        bbox=nsem_psa_user_export.bbox.wkt,
        date_filter=nsem_psa_user_export.date_filter,
        format=nsem_psa_user_export.format,
        url=nsem_psa_user_export.url,
    )

    text_body = """
        Your Post Storm Assessment export is complete.
        
        Storm: {storm}
        Date: {date_filter}
        Format: {format}
        Bounding Box: {bbox}
        Download Link: {url}
    """.format(**context)

    html_body = render_to_string('email_psa_user_export.html', context=context)

    # email the user
    send_mail(
        subject='Post Storm Assessment export: {}'.format(
            nsem_psa_user_export.nsem.named_storm),
        message=text_body,
        html_message=html_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[nsem_psa_user_export.user.email],
    )


@app.task(**TASK_ARGS)
def cache_psa_geojson_task(storm_id: int):
    """
    Automatically creates cached responses for a storm's PSA geojson results by crawling every api endpoint
    """

    qs = NsemPsa.objects.filter(named_storm__id=storm_id)
    if not qs.exists():
        logger.exception('There is not a PSA for storm id {}'.format(storm_id))
        raise

    nsem = qs.first()  # type: NsemPsa

    logger.info('Caching psa geojson for nsem psa {}'.format(nsem))

    # loop through every variable
    for psa_variable in nsem.nsempsavariable_set.all():  # type: NsemPsaVariable
        url = '{scheme}://{host}:{port}{path}'.format(
            scheme=settings.CWWED_SCHEME,
            host=settings.CWWED_HOST,
            port=settings.CWWED_PORT,
            path=reverse('psa-geojson', args=[storm_id]),
        )
        # request every date of the PSA for time-series variables
        if psa_variable.data_type == NsemPsaVariable.DATA_TYPE_TIME_SERIES:
            data = {
                'nsem_psa_variable': psa_variable.id
            }
            for nsem_date in nsem.dates:  # type: datetime
                data['date'] = nsem_date.strftime('%Y-%m-%dT%H:%M:%SZ')  # uses "Z" for zulu/UTC
                # send the raw query string so the date format doesn't get url encoded
                query = '&'.join(['{}={}'.format(key, value) for key, value in data.items()])
                r = requests.get('{}?{}'.format(url, query))
                logger.info('Cached {} with status {}'.format(r.url, r.status_code))
        # request once for max-values variable
        elif psa_variable.data_type == NsemPsaVariable.DATA_TYPE_MAX_VALUES:
            data = {
                'nsem_psa_variable': psa_variable.id
            }
            r = requests.get(url, data)
            logger.info('Cached {} with status {}'.format(r.url, r.status_code))
            logger.info(r.status_code)
