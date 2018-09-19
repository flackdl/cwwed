from __future__ import absolute_import, unicode_literals
import json
from datetime import datetime
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
import os
import tarfile
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse

from cwwed.celery import app
from named_storms.api.serializers import NSEMSerializer
from named_storms.data.processors import ProcessorData
from named_storms.models import NamedStorm, CoveredDataProvider, CoveredData, NamedStormCoveredDataLog, NSEM
from named_storms.utils import (
    processor_class, named_storm_covered_data_archive_path, copy_path_to_default_storage, named_storm_nsem_version_path,
    get_superuser_emails,
)


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
    :param nsem_id: id of NSEM record
    """

    # retrieve all the successful covered data by querying the logs
    # exclude any logs where the snapshot archive hasn't been created yet
    # sort by date descending and retrieve unique results
    nsem = get_object_or_404(NSEM, pk=int(nsem_id))
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
        default_storage.copy_within_storage(src_path, dest_path)

    nsem.covered_data_logs.set(logs_to_archive)  # many to many field
    nsem.covered_data_snapshot = storage_path
    nsem.save()

    return NSEMSerializer(instance=nsem).data


@app.task(**TASK_ARGS)
def extract_nsem_covered_data_task(nsem_data: dict):
    """
    Downloads and extracts nsem covered data into file storage
    :param nsem_data: dictionary of NSEM record
    """
    nsem = get_object_or_404(NSEM, pk=nsem_data['id'])
    file_system_path = os.path.join(
        named_storm_nsem_version_path(nsem),
        settings.CWWED_COVERED_DATA_DIR_NAME,
    )
    # download all the archives
    default_storage.download_directory(
        default_storage.path(nsem.covered_data_snapshot), file_system_path)

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
            nsem = NSEM.objects.filter(pk=args[0])
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


EXTRACT_NSEM_TASK_ARGS = TASK_ARGS.copy()
EXTRACT_NSEM_TASK_ARGS.update({
    'base': ExtractNSEMTaskBase,
})


@app.task(**EXTRACT_NSEM_TASK_ARGS)
def extract_nsem_model_output_task(nsem_id):
    """
    Downloads the model product output from object storage and puts it in file storage
    """

    nsem = get_object_or_404(NSEM, pk=int(nsem_id))
    uploaded_file_path = nsem.model_output_snapshot

    # verify this instance needs it's model output to be extracted (don't raise an exception to avoid this task retrying)
    if nsem.model_output_snapshot_extracted:
        return None
    elif not uploaded_file_path:
        raise Http404("Missing model output snapshot")
    # verify the uploaded output exists in storage
    elif not default_storage.exists(uploaded_file_path):
        raise Http404("{} doesn't exist in storage".format(uploaded_file_path))

    storage_path = os.path.join(
        settings.CWWED_NSEM_DIR_NAME,
        nsem.named_storm.name,
        'v{}'.format(nsem.id),
        settings.CWWED_NSEM_PSA_DIR_NAME,
        os.path.basename(uploaded_file_path),
    )

    # copy from "upload" directory to the versioned path
    default_storage.copy_within_storage(uploaded_file_path, storage_path)

    file_system_path = os.path.join(
        named_storm_nsem_version_path(nsem),
        settings.CWWED_NSEM_PSA_DIR_NAME,
        os.path.basename(uploaded_file_path),
    )

    # download to the file system
    default_storage.download_file(default_storage.path(storage_path), file_system_path)

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
    default_storage.delete(uploaded_file_path)

    return default_storage.url(storage_path)


@app.task(**TASK_ARGS)
def email_nsem_covered_data_complete_task(nsem_data: dict, base_url: str):
    """
    Email the "nsem" user indicating the Covered Data for a particular post storm assessment is complete and ready for download.
    :param nsem_data serialized NSEM instance
    :param base_url the scheme & domain that this request arrived
    """
    nsem = get_object_or_404(NSEM, pk=nsem_data['id'])
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
