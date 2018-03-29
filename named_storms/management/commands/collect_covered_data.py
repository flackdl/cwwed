import logging
import os
import shutil
from datetime import datetime
import celery
from named_storms.data.factory import NDBCProcessorFactory, ProcessorFactory, USGSProcessorFactory
from data_logs.models import NamedStormCoveredDataLog
from named_storms.models import NamedStorm, PROCESSOR_DATA_SOURCE_NDBC, PROCESSOR_DATA_SOURCE_USGS
from django.core.management.base import BaseCommand
from cwwed import slack
from named_storms.tasks import process_dataset
from named_storms.utils import named_storm_covered_data_incomplete_path, named_storm_covered_data_path, create_directory


class Command(BaseCommand):
    help = 'Collect Covered Data Snapshots'

    def handle(self, *args, **options):
        for storm in NamedStorm.objects.filter(active=True):

            self.stdout.write(self.style.SUCCESS('Named Storm: %s' % storm))

            # define and create output directories
            complete_path = named_storm_covered_data_path(storm)
            incomplete_path = named_storm_covered_data_incomplete_path(storm)
            stamped_path = os.path.join(
                complete_path,
                datetime.utcnow().strftime('%Y-%m-%d'),
            )
            create_directory(incomplete_path)
            create_directory(complete_path)
            create_directory(stamped_path, remove_if_exists=True)  # overwrite any existing directory so we can run multiple times in a day if necessary

            for data in storm.covered_data.filter(active=True):

                # TODO - each covered data collection should be in it's own task

                self.stdout.write(self.style.SUCCESS('\tCovered Data: %s' % data))

                covered_data_success = False

                for provider in data.covereddataprovider_set.filter(active=True):

                    log = NamedStormCoveredDataLog(
                        named_storm=storm,
                        covered_data=data,
                        provider=provider,
                    )

                    self.stdout.write(self.style.SUCCESS('\t\tProvider: %s' % provider))

                    if provider.processor == PROCESSOR_DATA_SOURCE_NDBC:
                        factory = NDBCProcessorFactory(storm, provider)
                    elif provider.processor == PROCESSOR_DATA_SOURCE_USGS:
                        factory = USGSProcessorFactory(storm, provider)
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

                    # fetch data in parallel but wait for all tasks to complete and captures results
                    task_group = celery.group([process_dataset.s(data) for data in processors_data])
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

                    log.success = covered_data_success

                    if covered_data_success:

                        # move the covered data outputs from the incomplete/staging directory to the date-stamped directory
                        shutil.move(os.path.join(incomplete_path, data.name), stamped_path)

                        # save the output in the log
                        log.snapshot = os.path.join(stamped_path, data.name)
                        log.save()

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

                    # save the log
                    log.save()

                if not covered_data_success:
                    slack.chat.post_message('#errors', 'Error collecting {} from ALL providers'.format(data))
