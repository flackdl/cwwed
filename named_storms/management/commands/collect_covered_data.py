import os
import shutil
from slacker import Slacker
from datetime import datetime
import celery
from django.conf import settings
from named_storms.data.factory import NDBCProcessorFactory, ProcessorFactory
from named_storms.models import NamedStorm, PROCESSOR_DATA_SOURCE_NDBC
from django.core.management.base import BaseCommand
from named_storms.tasks import process_dataset
from named_storms.utils import named_storm_covered_data_incomplete_path, named_storm_covered_data_path, create_directory, named_storm_covered_data_archive_path


class Command(BaseCommand):
    help = 'Collect Covered Data Snapshots'
    slack = Slacker(settings.SLACK_BOT_TOKEN)

    def handle(self, *args, **options):
        for storm in NamedStorm.objects.filter(active=True):

            self.stdout.write(self.style.SUCCESS('Named Storm: %s' % storm.name))

            for data in storm.covered_data.filter(active=True):

                self.stdout.write(self.style.SUCCESS('\tCovered Data: %s' % data))

                covered_data_success = False

                for provider in data.covereddataprovider_set.filter(active=True):

                    self.stdout.write(self.style.SUCCESS('\tProvider: %s' % provider))

                    if provider.processor.name == PROCESSOR_DATA_SOURCE_NDBC:
                        factory = NDBCProcessorFactory(storm, provider)
                    else:
                        factory = ProcessorFactory(storm, provider)

                    # fetch data in parallel but wait for all tasks to complete and captures results
                    task_group = celery.group([process_dataset.s(data) for data in factory.processors_data()])
                    group_result = task_group()
                    tasks_results = group_result.get()

                    for result in tasks_results:
                        self.stdout.write(self.style.WARNING('\tURL: %s' % result['url']))
                        self.stdout.write(self.style.WARNING('\tOutput: %s' % result['output_path']))

                    covered_data_success = group_result.successful()

                    if covered_data_success:
                        self.stdout.write(self.style.SUCCESS('\tSUCCESS'))
                        # skip additional providers since this was successful
                        break
                    else:
                        self.slack.chat.post_message('#errors', 'Error collecting {} from {}'.format(data, provider))
                        self.stdout.write(self.style.ERROR('\tFailed'))
                        self.stdout.write(self.style.WARNING('\tTrying next provider'))

                if not covered_data_success:
                    self.slack.chat.post_message('#errors', 'Error collecting {} from ALL providers'.format(data))

            #
            # move all covered data from the staging/incomplete directory to a date-stamped directory
            #

            incomplete_path = named_storm_covered_data_incomplete_path(storm)
            archive_path = named_storm_covered_data_archive_path(storm)
            stamped_path = '{}/{}'.format(
                archive_path,
                datetime.utcnow().strftime('%Y-%m-%d'),
            )

            # create directories
            create_directory(incomplete_path)
            create_directory(archive_path)
            create_directory(stamped_path, remove_if_exists=True)  # overwrite any existing directory so we can run multiple times in a day if necessary

            # move all covered data folders to stamped path
            for dir_name in os.listdir(incomplete_path):
                dir_path = os.path.join(incomplete_path, dir_name)
                shutil.move(dir_path, stamped_path)

            # create archive
            shutil.make_archive(
                base_name=stamped_path,
                format=settings.CWWED_COVERED_DATA_ARCHIVE_TYPE,
                root_dir=archive_path,
                base_dir=os.path.basename(stamped_path),
            )

