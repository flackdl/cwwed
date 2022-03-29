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
from django.contrib.gis.db.models import Collect, GeometryField, Func, F
from django.contrib.gis.db.models.functions import Intersection, MakeValid, AsKML, GeoHash
from django.core.exceptions import EmptyResultSet
from django.core.mail import send_mail
from django.db import connection
from django.db.models import CharField
from django.db.models.functions import Cast
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from geopandas import GeoDataFrame
from cwwed.celery import app
from cwwed.storage_backends import S3ObjectStoragePrivate
from named_storms.data.processors import ProcessorData
from named_storms.psa.processor import PsaDatasetProcessor
from named_storms.models import (
    NamedStorm, CoveredDataProvider, CoveredData, NamedStormCoveredDataLog, NsemPsa, NsemPsaUserExport,
    NsemPsaContour, NsemPsaVariable, NamedStormCoveredDataSnapshot, NsemPsaManifestDataset, NsemPsaData)
from named_storms.psa.validator import PsaDatasetValidator
from named_storms.utils import (
    processor_class, copy_path_to_default_storage, get_superuser_emails,
    named_storm_nsem_version_path, root_data_path, create_directory,
    get_geojson_feature_collection_from_psa_qs, named_storm_path,
    named_storm_covered_data_current_path)

# celery logger
logger = get_task_logger(__name__)


TASK_ARGS_RETRY = dict(
    autoretry_for=(Exception,),
    default_retry_delay=5,
    max_retries=3,
)

TASK_ARGS_ACK_LATE = dict(
    # acknowledge completion after task has been fully executed vs just before because
    # this guarantees the task will retry if the worker crashes which can happen during cluster auto scaling
    # https://docs.celeryproject.org/en/stable/reference/celery.app.task.html#celery.app.task.Task.acks_late
    acks_late=True,
    # re-queue even if a child process is killed (kubernetes evicts pods for various reasons)
    # https://docs.celeryproject.org/en/latest/userguide/configuration.html#std-setting-task_reject_on_worker_lost
    task_reject_on_worker_lost=True,
)


@app.task(**TASK_ARGS_RETRY)
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


@app.task(**TASK_ARGS_RETRY)
def process_covered_data_dataset_task(data: list):
    """
    Run the covered data dataset processor
    """
    processor_data = ProcessorData(*data)
    named_storm = get_object_or_404(NamedStorm, pk=processor_data.named_storm_id)
    provider = get_object_or_404(CoveredDataProvider, pk=processor_data.provider_id)

    # use override if it exists
    if processor_data.override_provider_processor_class is not None:
        processor_cls = processor_class(processor_data.override_provider_processor_class)
    # otherwise look up the processor source on the provider
    else:
        processor_cls = processor_class(provider.processor_source)

    # build processor
    processor = processor_cls(
        named_storm=named_storm,
        provider=provider,
        url=processor_data.url,
        label=processor_data.label,
        group=processor_data.group,
        **processor_data.kwargs,  # include any extra kwargs
    )
    # fetch and return data
    processor.fetch()
    return processor.to_dict()


@app.task(**TASK_ARGS_RETRY)
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


@app.task(**TASK_ARGS_RETRY)
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


@app.task(**TASK_ARGS_RETRY, queue=settings.CWWED_QUEUE_PROCESS_PSA)
def extract_named_storm_covered_data_snapshot_task(nsem_psa_id):
    """
    Downloads and extracts a named storm covered data snapshot into file storage
    """
    nsem_psa = get_object_or_404(NsemPsa, pk=nsem_psa_id)

    # only extract if the psa was validated
    if not nsem_psa.validated:
        logger.warning('{} was not validated so skipping covered data extraction'.format(nsem_psa))
        return None

    file_system_path = os.path.join(
        named_storm_path(nsem_psa.named_storm),
        settings.CWWED_COVERED_DATA_SNAPSHOTS_DIR_NAME,
        str(nsem_psa.covered_data_snapshot.id),
    )

    # download all the archives
    storage = S3ObjectStoragePrivate()
    storage.download_directory(
        storage.path(nsem_psa.covered_data_snapshot.path), file_system_path)

    # extract the archives
    for file in os.listdir(file_system_path):
        if file.endswith(settings.CWWED_ARCHIVE_EXTENSION):
            file_path = os.path.join(file_system_path, file)
            tar = tarfile.open(file_path, settings.CWWED_NSEM_ARCHIVE_READ_MODE)
            tar.extractall(file_system_path)
            tar.close()
            # remove the original archive now that it's extracted
            os.remove(file_path)

    return nsem_psa.covered_data_snapshot.id


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


EXTRACT_NSEM_TASK_ARGS = TASK_ARGS_RETRY.copy()  # type: dict
EXTRACT_NSEM_TASK_ARGS.update({
    'base': ExtractNSEMTaskBase,
})


@app.task(**EXTRACT_NSEM_TASK_ARGS, queue=settings.CWWED_QUEUE_PROCESS_PSA)
def extract_nsem_psa_task(nsem_id):
    """
    Downloads the model product output from object storage and puts it in file storage
    """

    nsem = get_object_or_404(NsemPsa, pk=int(nsem_id))
    uploaded_file_path = nsem.path
    storage = S3ObjectStoragePrivate()  # deploy-specific prefix (dev, alpha, etc)
    root_storage = S3ObjectStoragePrivate(force_root_location=True)

    # verify this instance needs it's model output to be extracted (don't raise an exception to avoid this task retrying)
    if nsem.extracted:
        return None
    elif not uploaded_file_path:
        raise Http404("Missing model output")
    # verify the uploaded output exists in storage
    elif not root_storage.exists(uploaded_file_path):
        raise Http404("{} doesn't exist in storage".format(uploaded_file_path))

    storage_path = os.path.join(
        settings.CWWED_NSEM_DIR_NAME,
        nsem.named_storm.name,
        str(nsem.id),
        os.path.basename(uploaded_file_path),
    )

    # copy from "upload" directory to the deploy-specific versioned path
    root_storage.copy_within_storage(uploaded_file_path, os.path.join(storage.location, storage_path))

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


@app.task(**TASK_ARGS_RETRY)
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


@app.task(queue=settings.CWWED_QUEUE_PROCESS_PSA)
def postprocess_psa_validated_task(nsem_psa_id):
    """
    Email the "nsem" user indicating whether the PSA has been validated or not
    Raise exception if the PSA wasn't validated
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

    if not nsem_psa.validated:
        raise Exception('PSA {} was not validated'.format(nsem_psa))


@app.task(queue=settings.CWWED_QUEUE_PROCESS_PSA)
def validate_nsem_psa_task(nsem_id):
    """
    Validates the PSA from file storage with the following:
    - cf conventions - http://cfconventions.org/
    - ugrid conventions - http://ugrid-conventions.github.io/ugrid-conventions/
    - expected coordinates in dataset
    - supplied dates exist in dataset
    - supplied variables exist in dataset
    - proper time dimension & timezone (xarray throws ValueError if it can't decode it automatically)
    - duplicate dimension & scalar values (xarray throws ValueError if encountered)
    - netcdf only
    """

    # TODO - validate expected units per variable

    valid_files = []
    exceptions = {
        'global': [],
        'files': {},
    }

    nsem_psa = get_object_or_404(NsemPsa, pk=int(nsem_id))

    psa_base_path = named_storm_nsem_version_path(nsem_psa)

    for dataset in nsem_psa.nsempsamanifestdataset_set.all():
        file_path = os.path.join(psa_base_path, dataset.path)
        file_exceptions = []
        variable_exceptions = {}
        try:
            ds = xr.open_dataset(file_path)
        except (ValueError, OSError) as e:
            file_exceptions.append(str(e))
        else:

            # cf conventions
            cf_check = cfchecks.CFChecker(silent=True)
            cf_check.checker(file_path)
            file_exceptions += cf_check.results['global']['FATAL']
            file_exceptions += cf_check.results['global']['ERROR']
            for variable, result in cf_check.results['variables'].items():
                if result['FATAL'] or result['ERROR']:
                    variable_exceptions[variable] = result['FATAL'] + result['ERROR']

            validator = PsaDatasetValidator(ds)

            # dates
            for date in nsem_psa.naive_dates():
                if not validator.is_valid_date(date):
                    file_exceptions.append('Manifest date was not found in actual dataset: {}'.format(date))

            # coordinates
            if not validator.is_valid_coords():
                file_exceptions.append('Missing required coordinates: {}'.format(validator.required_coords))

            # variables
            if not validator.is_valid_variables(dataset.variables):
                file_exceptions.append('Manifest dataset variables were not found in actual dataset')

            # structured grid
            if dataset.structured:
                if not validator.is_valid_structured():
                    file_exceptions.append(
                        'dataset is identified as structured but variable does not have the right shape')
            # unstructured grid - http://ugrid-conventions.github.io/ugrid-conventions/
            else:
                if not validator.is_valid_unstructured_topology(dataset.topology_name):
                    file_exceptions.append('topology_name "{}" missing from dataset'.format(dataset.topology_name))
                elif not validator.is_valid_unstructured_start_index(dataset.topology_name):
                    file_exceptions.append('start_index attribute missing from topology name "{}"'.format(dataset.topology_name))

        if file_exceptions or variable_exceptions:
            e = {'file': file_exceptions, 'variables': variable_exceptions}
            exceptions['files'][dataset.path] = e
        else:
            valid_files.append(dataset.path)

    if not valid_files:
        exceptions['global'] = ['no valid files found']

    # error
    if exceptions['global'] or exceptions['files']:
        nsem_psa.validation_exceptions = exceptions
    # success
    else:
        nsem_psa.validated = True

    nsem_psa.date_validation = datetime.utcnow().replace(tzinfo=pytz.utc)
    nsem_psa.save()


@app.task(**TASK_ARGS_RETRY)
def create_psa_user_export_task(nsem_psa_user_export_id: int):

    nsem_psa_user_export = get_object_or_404(NsemPsaUserExport, id=nsem_psa_user_export_id)
    nsem_psa = nsem_psa_user_export.nsem

    date_expires = pytz.utc.localize(datetime.utcnow()) + timedelta(days=settings.CWWED_PSA_USER_DATA_EXPORT_DAYS)

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

    # netcdf/csv - extract raw point data
    if nsem_psa_user_export.format in [NsemPsaUserExport.FORMAT_NETCDF, NsemPsaUserExport.FORMAT_CSV]:

        # csv exports to a specific date while netcdf includes all
        dates_to_export = [nsem_psa_user_export.date_filter] if nsem_psa_user_export.format == NsemPsaUserExport.FORMAT_CSV else nsem_psa.dates

        for psa_dataset in nsem_psa_user_export.nsem.nsempsamanifestdataset_set.all():

            # create export dataset including any supplied metadata from the manifest
            ds_out = xr.Dataset(attrs=psa_dataset.meta)

            ds_out_path = os.path.join(tmp_user_export_path, psa_dataset.path)  # dataset extension is expected to already be .nc

            # filter points within the user's bounding box
            all_data = NsemPsaData.objects.annotate(
                geo_hash=GeoHash('point'),
                geom_point=Cast('point', GeometryField()),
            ).filter(
                nsem_psa_variable__name__in=psa_dataset.variables,
                nsem_psa_variable__nsem=nsem_psa,
                geom_point__within=nsem_psa_user_export.bbox,
            ).distinct(
                'geo_hash',
            ).order_by(
                'geo_hash',
            ).only(
                'point',
            )

            # export's bounding box didn't contain any points/data
            if not all_data.exists():
                continue

            all_points = [d.point for d in all_data]

            # build the dataset coordinates
            coords = np.array([p.coords for p in all_points])
            ds_coords = {
                'time': (['time'], dates_to_export),
                'lon': (['node'], coords[:, 0]),
                'lat': (['node'], coords[:, 1]),
            }

            # add every time-series variable to the out dataset for this psa dataset
            variable_kwargs = dict(
                data_type=NsemPsaVariable.DATA_TYPE_TIME_SERIES,
                name__in=psa_dataset.variables,
            )
            for psa_variable in psa_dataset.nsem.nsempsavariable_set.filter(**variable_kwargs):

                # build results for data in each date in the psa
                results = []
                for date in dates_to_export:
                    variable_data = psa_variable.nsempsadata_set.annotate(
                        geo_hash=GeoHash('point'),
                    ).filter(
                        geo_hash__in=[d.geo_hash for d in all_data],
                        date=date,
                    ).only(
                        'value',
                        'point',
                    ).order_by(
                        'geo_hash',
                    )
                    variable_data = list(variable_data)
                    variable_points = [d.point for d in variable_data]
                    result = []

                    # iterate over point/data list and insert NaN for absent values
                    for point in all_points:
                        try:
                            idx = variable_points.index(point)
                        # no value at this point
                        except ValueError:
                            result.append(np.nan)
                        # insert value for this located point
                        else:
                            result.append(variable_data[idx].value)
                            # remove found object from lists
                            variable_data.pop(idx)
                            variable_points.pop(idx)

                    results.append(result)

                # add the data array to the dataset
                ds_out[psa_variable.name] = xr.DataArray(
                    np.array(results),
                    coords=ds_coords,
                    dims=['time', 'node'],
                    attrs=psa_variable.meta,
                )

            # include metadata for space and time
            ds_out.time.attrs = psa_dataset.meta_time
            ds_out.lat.attrs = psa_dataset.meta_lat
            ds_out.lon.attrs = psa_dataset.meta_lon

            # netcdf
            if nsem_psa_user_export.format == NsemPsaUserExport.FORMAT_NETCDF:
                ds_out.to_netcdf(ds_out_path)

            # csv
            elif nsem_psa_user_export.format == NsemPsaUserExport.FORMAT_CSV:

                # create pandas DataFrame which makes a csv conversion very simple
                df_out = pd.DataFrame()

                # multi index of date/lon/lat
                index = pd.MultiIndex.from_arrays([
                    np.full(len(ds_out.node), nsem_psa_user_export.date_filter),
                    ds_out['lon'],
                    ds_out['lat'],
                ])

                # insert a new column for each variable to df_out
                for variable in ds_out.data_vars:

                    # convert data array to a panda dataframe
                    df = ds_out[variable].to_dataframe()

                    # set the multi index
                    df.set_index(index, inplace=True)

                    # insert df as a new column
                    df_out.insert(len(df_out.columns), variable, df[variable])

                # drop rows without any data (could contain non time-series variables)
                df_out.dropna(how='all', inplace=True)

                # write csv
                df_out.to_csv(
                    os.path.join(tmp_user_export_path, '{}.csv'.format(psa_dataset.path)))

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

            qs = NsemPsaContour.objects.filter(**kwargs)
            data_ids = [r['id'] for r in qs.values('id')]

            # group all intersecting geometries together by value and clip the result using the export's bbox intersection
            # cast to CharField for GeoPandas
            # use ST_MakeValid due to ring self-intersections which ST_Intersection chokes on
            # use ST_CollectionHomogenize to guarantee we only get (multi)geometries
            qs = NsemPsaContour.objects.filter(id__in=data_ids)
            qs = qs.values('value')
            qs = qs.annotate(
                geom=Cast(
                        Func(
                            Collect(Intersection(MakeValid(Cast('geo', GeometryField())), nsem_psa_user_export.bbox)),
                            function='ST_CollectionHomogenize',
                        ),
                        CharField()
                ),
            )

            # create GeoDataFrame from query
            try:
                gdf = GeoDataFrame.from_postgis(str(qs.query), connection, geom_col='geom')
            # https://docs.djangoproject.com/en/3.0/ref/exceptions/#emptyresultset
            except EmptyResultSet:
                logger.info('empty result for {}', psa_geom_variable)
                continue

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
            # NOTE: using ST_MakeValid to fix any ring self-intersections which ST_Intersection chokes on
            qs = psa_variable.nsempsacontour_set.filter(**data_kwargs)
            qs = qs.values(*[
                'value', 'color', 'date', 'nsem_psa_variable__name', 'nsem_psa_variable__display_name',
                'nsem_psa_variable__units', 'nsem_psa_variable__data_type',
            ])
            qs = qs.annotate(geom=Collect(Intersection(MakeValid(Cast('geo', GeometryField())), nsem_psa_user_export.bbox)))

            # export's bounding box didn't contain any points/data
            if not qs.exists():
                continue

            if nsem_psa_user_export.format == NsemPsaUserExport.FORMAT_KML:
                # annotate with "AsKML" to get kml and "ST_CollectionHomogenize" to guarantee we only get (multi)geometries
                qs = qs.annotate(kml=AsKML(Func(F('geom'), function='ST_CollectionHomogenize')))
                # write kml to file
                with open(os.path.join(tmp_user_export_path, '{}.kml'.format(psa_variable.name)), 'w') as fh:
                    fh.write(render_to_string('psa_export.kml', context={"results": qs, "psa_variable": psa_variable}))
            elif nsem_psa_user_export.format == NsemPsaUserExport.FORMAT_GEOJSON:
                # write geojson to file
                with open(os.path.join(tmp_user_export_path, '{}.json'.format(psa_variable.name)), 'w') as fh:
                    fh.write(get_geojson_feature_collection_from_psa_qs(qs))

    # no data found in the export's bounding box
    if len(os.listdir(tmp_user_export_path)) == 0:
        msg = "No data found in the export's bounding box."
        logger.warning(msg)
        # update export instance
        nsem_psa_user_export.date_completed = pytz.utc.localize(datetime.utcnow())
        nsem_psa_user_export.exception = msg
        nsem_psa_user_export.save()
        return

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
    key_name = '{path}/{storm_name}-{export_id}.{extension}'.format(
        path=settings.CWWED_NSEM_S3_USER_EXPORT_DIR_NAME,
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

    nsem_psa_user_export.success = True
    nsem_psa_user_export.date_expires = date_expires
    nsem_psa_user_export.date_completed = pytz.utc.localize(datetime.utcnow())
    nsem_psa_user_export.url = presigned_url
    nsem_psa_user_export.save()


@app.task(**TASK_ARGS_RETRY)
def email_psa_user_export_task(nsem_psa_user_export_id: int):
    nsem_psa_user_export = get_object_or_404(NsemPsaUserExport, id=nsem_psa_user_export_id)

    if nsem_psa_user_export.success:
        msg = 'Your Post Storm Assessment export is complete.'
    else:
        msg = nsem_psa_user_export.exception or 'There was no data found within the specified selection.'

    context = dict(
        msg=msg,
        storm=nsem_psa_user_export.nsem.named_storm,
        bbox=nsem_psa_user_export.bbox.wkt,
        date_filter=nsem_psa_user_export.date_filter,
        format=nsem_psa_user_export.format,
        url=nsem_psa_user_export.url,
    )

    text_body = """
        {msg}
        
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


@app.task(**TASK_ARGS_RETRY, queue=settings.CWWED_QUEUE_PROCESS_PSA)
def cache_psa_contour_task(storm_id: int):
    """
    Automatically creates cached responses for a storm's PSA contour results by crawling every api endpoint
    """

    nsem = NsemPsa.get_last_valid_psa(storm_id=storm_id)  # type: NsemPsa
    if not nsem:
        logger.exception('There is not a valid PSA for storm id {}'.format(storm_id))
        raise

    logger.info('Caching psa geojson for nsem psa {}'.format(nsem))

    # loop through every polygon variable
    for psa_variable in nsem.nsempsavariable_set.filter(geo_type=NsemPsaVariable.GEO_TYPE_POLYGON):  # type: NsemPsaVariable
        url = '{scheme}://{host}:{port}{path}'.format(
            scheme=settings.CWWED_SCHEME,
            host=settings.CWWED_HOST,
            port=settings.CWWED_PORT,
            path=reverse('psa-contour', args=[storm_id]),
        )
        # request every date of the PSA for time-series variables
        if psa_variable.data_type == NsemPsaVariable.DATA_TYPE_TIME_SERIES:
            data = {
                'nsem_psa_variable': psa_variable.name,
                '_cacheId': nsem.id,  # using psa as cache busting parameter
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
                'nsem_psa_variable': psa_variable.name,
            }
            r = requests.get(url, data)
            logger.info('Cached {} with status {}'.format(r.url, r.status_code))
            logger.info(r.status_code)


@app.task(**TASK_ARGS_RETRY, **TASK_ARGS_ACK_LATE, queue=settings.CWWED_QUEUE_PROCESS_PSA)
def ingest_nsem_psa_dataset_variable_task(psa_dataset_id: int, variable: str, date: datetime = None):
    """
    Ingests an NSEM PSA Dataset variable into CWWED
    """
    dataset_manifest = get_object_or_404(NsemPsaManifestDataset, pk=psa_dataset_id)
    assert variable in dataset_manifest.variables, 'Variable not found in {}'.format(dataset_manifest)
    PsaDatasetProcessor(psa_manifest_dataset=dataset_manifest).ingest_variable(variable, date)
    logger.info('{}: {} variable (date={}) has been successfully ingested'.format(dataset_manifest, variable, date))


@app.task(**TASK_ARGS_RETRY, queue=settings.CWWED_QUEUE_PROCESS_PSA)
def postprocess_psa_ingest_task(nsem_psa_id: int, success: bool):
    """
    Update the psa as processed and email the "nsem" user indicating the PSA has been ingested
    """
    nsem_psa = get_object_or_404(NsemPsa, pk=nsem_psa_id)
    nsem_user = User.objects.get(username=settings.CWWED_NSEM_USER)
    nsem_psa_api_url = "{}://{}:{}{}".format(
        settings.CWWED_SCHEME, settings.CWWED_HOST, settings.CWWED_PORT, reverse('nsempsa-detail', args=[nsem_psa.id]))

    # save the dataset's metadata in the psa manifest dataset
    for psa_manifest_dataset in nsem_psa.nsempsamanifestdataset_set.all():
        psa_processor = PsaDatasetProcessor(psa_manifest_dataset)
        psa_manifest_dataset.meta = psa_processor.get_metadata()
        psa_manifest_dataset.meta_time = psa_processor.get_variable_metadata('time')
        psa_manifest_dataset.meta_lat = psa_processor.get_variable_metadata('lat')
        psa_manifest_dataset.meta_lon = psa_processor.get_variable_metadata('lon')
        psa_manifest_dataset.save()

    # save psa as processed
    nsem_psa.processed = success
    nsem_psa.date_processed = timezone.now()
    nsem_psa.save()

    msg = 'PSA {psa} {msg}'.format(
        msg='has been successfully ingested' if success else 'failed during ingestion',
        psa=nsem_psa,
    )

    logger.info(msg)

    context = dict(
        msg=msg,
        nsem_psa=nsem_psa,
        api_url=nsem_psa_api_url,
    )

    body = """
        {msg}.

        API: {api_url}
        """.format(**context)

    html_body = render_to_string('email_psa_ingested.html', context=context)

    # include the "nsem" user and all super users
    recipients = get_superuser_emails()
    if nsem_user.email:
        recipients.append(nsem_user.email)

    send_mail(
        subject=msg,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        html_message=html_body,
    )
    return nsem_psa.id
