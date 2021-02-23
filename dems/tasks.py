from celery import chain
from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string

from cwwed.celery import app
from dems.models import DemSource, DemSourceLog
from dems.processor import DemSourceProcessor

# celery logger
from named_storms.utils import get_superuser_emails

logger = get_task_logger(__name__)


@app.task()
def update_dems():
    chain(
        # update dems from their sources
        update_dems_list_task.si(),
        # update individual dem raster meta data
        update_dems_data_task.si(),
        # email dem updates
        email_updated_dems_task.si(),
    )()


@app.task()
def update_dems_list_task():
    for dem_source in DemSource.objects.all():
        processor = DemSourceProcessor(dem_source)
        processor.update_list()


@app.task()
def update_dems_data_task():
    # update any dems that changed
    for dem_source in DemSource.objects.all():
        processor = DemSourceProcessor(dem_source)
        logger.info('updating dem data for source {}'.format(dem_source))
        # use log from most recent scan
        dem_source_log = dem_source.demsourcelog_set.order_by('-date_scanned').first()  # type: DemSourceLog
        logger.info('found dems that were updated from log {}'.format(dem_source_log))
        for dem in dem_source.dem_set.filter(path__in=dem_source_log.dems_updated + dem_source_log.dems_added):
            logger.info('updating dem data for {}'.format(dem))
            processor.update_dem_data(dem)


@app.task()
def email_updated_dems_task():
    updated_dem_source_logs = []
    for dem_source in DemSource.objects.all():
        dem_source_log = dem_source.demsourcelog_set.order_by('-date_scanned').first()  # type: DemSourceLog
        # source log has updated
        if any([dem_source_log.dems_added, dem_source_log.dems_updated, dem_source_log.dems_removed]):
            updated_dem_source_logs.append(dem_source_log)

    # has updates so send email
    if updated_dem_source_logs:
        recipients = get_superuser_emails()
        nsem_user = User.objects.get(username=settings.CWWED_NSEM_USER)
        if nsem_user.email:
            recipients.append(nsem_user.email)

        body = render_to_string(
            'email_dem_updated.html',
            context={
                "scheme_and_host": 'http{secure}://{host}{port}'.format(
                    secure='s' if not settings.DEBUG else '',
                    port='' if not settings.DEBUG else ':{}'.format(settings.CWWED_PORT),
                    host=settings.CWWED_HOST),
                "updated_dem_source_logs": updated_dem_source_logs,
            })

        send_mail(
            subject='DEMs have been updated',
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            html_message=body,
        )
    else:
        logger.info('no dem updates detected')
