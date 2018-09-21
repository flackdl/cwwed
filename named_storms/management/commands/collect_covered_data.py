import logging
import os
import shutil
import celery
from django.core.management.base import BaseCommand
from named_storms.data.factory import ProcessorFactory
from named_storms.models import NamedStorm, NamedStormCoveredDataLog
from named_storms.tasks import process_dataset_task, archive_named_storm_covered_data_task
from named_storms.utils import named_storm_covered_data_incomplete_path, named_storm_covered_data_path, create_directory, processor_factory_class, slack_channel


class Command(BaseCommand):
    help = 'Collect Covered Data Snapshots'

    def add_arguments(self, parser):
        parser.add_argument('--storm_id', type=int)
        parser.add_argument('--covered_data_id', type=int)

    def handle(self, *args, **options):
        storm_filter_args = {'active': True}
        covered_data_filter_args = {'active': True}

        # optional arguments
        if options.get('storm_id'):
            storm_filter_args.update(id=options['storm_id'])
        if options.get('covered_data_id'):
            covered_data_filter_args.update(id=options['covered_data_id'])

        for storm in NamedStorm.objects.filter(**storm_filter_args):

            self.stdout.write(self.style.SUCCESS('Named Storm: %s' % storm))

            # create output directories
            complete_path = named_storm_covered_data_path(storm)
            incomplete_path = named_storm_covered_data_incomplete_path(storm)
            create_directory(complete_path)
            create_directory(incomplete_path, remove_if_exists=True)

            for data in storm.covered_data.filter(**covered_data_filter_args):

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

                    factory_cls = processor_factory_class(provider)
                    factory = factory_cls(storm, provider)  # type: ProcessorFactory

                    # fetch all the processors data
                    try:
                        processors_data = factory.processors_data()
                    except Exception as e:
                        # failed building processors data so log error and skip this provider
                        logging.error('Error building factory for {} \n{}'.format(provider, e))
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
                        logging.error('Error running tasks for {} \n{}'.format(provider, e))
                        log.success = False
                        log.exception = str(e)
                        log.save()
                        continue

                    covered_data_success = group_result.successful()

                    # save the log
                    log.success = covered_data_success
                    log.save()

                    if covered_data_success:

                        data_path = os.path.join(complete_path, data.name)
                        data_path_incomplete = os.path.join(incomplete_path, data.name)

                        try:
                            # remove any previous version in the complete path
                            if os.path.exists(data_path):
                                shutil.rmtree(data_path)
                            # move the covered data outputs from the incomplete/staging directory to the complete directory
                            shutil.move(data_path_incomplete, complete_path)
                        except OSError as e:
                            logging.error('Error moving path for {} \n{}'.format(provider, e))
                            log.success = False
                            log.exception = str(e)
                            log.save()
                            continue

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
                        logging.error('Error collecting {} from {}'.format(data, provider))
                        self.stdout.write(self.style.ERROR('\t\tFailed'))
                        self.stdout.write(self.style.WARNING('\t\tTrying next provider'))

                if not covered_data_success:
                    logging.error('Error collecting {} from ALL providers'.format(data))

        slack_channel('Finished collecting covered data', '#events')
