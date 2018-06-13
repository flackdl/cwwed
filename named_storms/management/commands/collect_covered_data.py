import logging
import os
import shutil
import celery
from django.core.management.base import BaseCommand
from named_storms.data.factory import NDBCProcessorFactory, ProcessorFactory, USGSProcessorFactory, JPLQSCATL1CProcessorFactory
from named_storms.models import (
    NamedStorm, PROCESSOR_DATA_FACTORY_USGS, NamedStormCoveredDataLog,
    PROCESSOR_DATA_FACTORY_JPL_QSCAT_L1C, PROCESSOR_DATA_FACTORY_NDBC,
)
from cwwed import slack
from named_storms.tasks import process_dataset_task, archive_named_storm_covered_data_task
from named_storms.utils import named_storm_covered_data_incomplete_path, named_storm_covered_data_path, create_directory


class Command(BaseCommand):
    help = 'Collect Covered Data Snapshots'

    def handle(self, *args, **options):
        for storm in NamedStorm.objects.filter(active=True):

            self.stdout.write(self.style.SUCCESS('Named Storm: %s' % storm))

            # create output directories
            complete_path = named_storm_covered_data_path(storm)
            incomplete_path = named_storm_covered_data_incomplete_path(storm)
            create_directory(complete_path)
            create_directory(incomplete_path, remove_if_exists=True)

            for data in storm.covered_data.filter(active=True):

                # TODO - each covered data collection should be in it's own task

                self.stdout.write(self.style.SUCCESS('\tCovered Data: %s' % data))

                covered_data_success = False

                providers = data.covereddataprovider_set.filter(active=True)

                if not providers.exists():
                    # no need to continue if there aren't any active providers for this covered data
                    self.stdout.write(self.style.WARNING('\t\tNo providers available.  Skipping this covered data'))
                    continue

                for provider in providers:

                    log = NamedStormCoveredDataLog(
                        named_storm=storm,
                        covered_data=data,
                        provider=provider,
                    )

                    self.stdout.write(self.style.SUCCESS('\t\tProvider: %s' % provider))

                    # instantiate the right processor factory
                    if provider.processor_factory == PROCESSOR_DATA_FACTORY_NDBC:
                        factory = NDBCProcessorFactory(storm, provider)
                    elif provider.processor_factory == PROCESSOR_DATA_FACTORY_USGS:
                        factory = USGSProcessorFactory(storm, provider)
                    elif provider.processor_factory == PROCESSOR_DATA_FACTORY_JPL_QSCAT_L1C:
                        factory = JPLQSCATL1CProcessorFactory(storm, provider)
                    else:
                        factory = ProcessorFactory(storm, provider)

                    # fetch all the processors data
                    try:
                        processors_data = factory.processors_data()
                    except Exception as e:
                        # failed building processors data so log error and skip this provider
                        slack.chat.post_message('#errors', 'Error building factory for {} \n{}'.format(provider, e))
                        logging.exception(e)
                        # save the log
                        log.success = False
                        log.exception = str(e)
                        log.save()
                        continue

                    if not processors_data:
                        self.stdout.write(self.style.WARNING('\t\tNo data provided.  Skipping provider'))
                        continue

                    # fetch data in parallel but wait for all tasks to complete and capture results
                    task_group = celery.group([process_dataset_task.s(data) for data in processors_data])
                    group_result = task_group()

                    # we must handle exceptions from the actual results
                    try:
                        tasks_results = group_result.get()
                    except Exception as e:
                        # failed running processor tasks so log error and skip this provider
                        slack.chat.post_message('#errors', 'Error running tasks for {} \n{}'.format(provider, e))
                        logging.exception(e)
                        log.success = False
                        log.exception = str(e)
                        log.save()
                        continue

                    covered_data_success = group_result.successful()

                    # save the log
                    log.success = covered_data_success
                    log.save()

                    if covered_data_success:

                        # remove any previous version in the complete path
                        shutil.rmtree(os.path.join(complete_path, data.name), ignore_errors=True)

                        # then move the covered data outputs from the incomplete/staging directory to the complete directory
                        shutil.move(os.path.join(incomplete_path, data.name), complete_path)

                        # create a task to archive the data
                        archive_named_storm_covered_data_task.delay(
                            named_storm_id=storm.id,
                            covered_data_id=data.id,
                            log_id=log.id,
                        )

                        # debug/output
                        for result in tasks_results:
                            self.stdout.write(self.style.WARNING('\t\tURL: %s' % result['url']))
                            self.stdout.write(self.style.WARNING('\t\tOutput: %s' % result['output_path']))

                        self.stdout.write(self.style.SUCCESS('\t\tSUCCESS'))

                        # skip additional providers since this was successful
                        break
                    else:
                        slack.chat.post_message('#errors', 'Error collecting {} from {}'.format(data, provider))
                        self.stdout.write(self.style.ERROR('\t\tFailed'))
                        self.stdout.write(self.style.WARNING('\t\tTrying next provider'))

                if not covered_data_success:
                    slack.chat.post_message('#errors', 'Error collecting {} from ALL providers'.format(data))
