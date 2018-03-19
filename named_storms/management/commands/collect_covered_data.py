import os
import shutil
from datetime import datetime
import celery
from django.conf import settings
from named_storms.data.factory import NDBCProcessorFactory, ProcessorFactory
from named_storms.models import NamedStorm, PROCESSOR_DATA_SOURCE_NDBC
from django.core.management.base import BaseCommand
from named_storms.tasks import process_dataset
from named_storms.utils import named_storm_covered_data_incomplete_path, named_storm_covered_data_path, create_directory


class Command(BaseCommand):
    help = 'Collect Covered Data Snapshots'

    def handle(self, *args, **options):
        for storm in NamedStorm.objects.filter(active=True):

            self.stdout.write(self.style.SUCCESS('Named Storm: %s' % storm.name))

            for data in storm.covered_data.filter(active=True):

                self.stdout.write(self.style.SUCCESS('\tCovered Data: %s' % data))

                provider_success = False

                for provider in data.covereddataprovider_set.filter(active=True):

                    self.stdout.write(self.style.SUCCESS('\tProvider: %s' % provider))

                    if provider.processor.name == PROCESSOR_DATA_SOURCE_NDBC:
                        factory = NDBCProcessorFactory(storm, provider)
                    else:
                        factory = ProcessorFactory(storm, provider)

                    task_group = celery.group([process_dataset.s(data) for data in factory.processors_data()])
                    group_result = task_group()
                    tasks_results = group_result.get()  # waits for all tasks to complete and captures results

                    for result in tasks_results:
                        self.stdout.write(self.style.WARNING('\tURL: %s' % result['url']))
                        self.stdout.write(self.style.WARNING('\tOutput: %s' % result['output_path']))

                    provider_success = group_result.successful()

                    if provider_success:
                        self.stdout.write(self.style.SUCCESS('\tSUCCESS'))
                        # skip additional providers since this was successful
                        break
                    else:
                        self.stdout.write(self.style.ERROR('\tFailed'))
                        self.stdout.write(self.style.WARNING('\tTrying next provider'))

                if provider_success:
                    # move all covered data from the staging/incomplete directory to a date stamped directory
                    # TODO put in task

                    incomplete_path = named_storm_covered_data_incomplete_path(storm)
                    complete_path = named_storm_covered_data_path(storm)
                    stamped_path = '{}/{}'.format(
                        complete_path,
                        datetime.utcnow().strftime('%Y-%m-%d'),
                    )

                    # create date stamped path
                    create_directory(stamped_path, remove_if_exists=True)

                    # move all covered data folders to stamped path
                    for dir_name in os.listdir(incomplete_path):
                        dir_path = os.path.join(incomplete_path, dir_name)
                        shutil.move(dir_path, stamped_path)

                    # create archive
                    shutil.make_archive(
                        base_name=stamped_path,
                        format='gztar',
                        root_dir=complete_path,
                        base_dir=os.path.basename(stamped_path),
                    )

                    # update "current" symlink to date stamped directory, but
                    # first create a temporary link and rename it so it's an atomic operation
                    symlink = '{}/{}'.format(complete_path, settings.CWWED_COVERED_DATA_CURRENT_DIR_NAME)
                    tmp_symlink = '{}.tmp'.format(symlink)
                    os.symlink(
                        stamped_path,
                        tmp_symlink,
                    )
                    os.rename(tmp_symlink, symlink)

                else:
                    # TODO
                    pass
