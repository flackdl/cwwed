import os
import shlex
import subprocess
from django.core.management.base import BaseCommand
from django.utils import autoreload


"""
This is used for development only.  It starts celery and flower and hot reloads on file changes
"""


def restart_celery():
    # kill celery/flower
    cmd = 'pkill celery'
    subprocess.call(shlex.split(cmd))

    # include the current environment
    env = os.environ.copy()

    # start celery
    cmd = 'celery -A cwwed worker -l info --queues celery,process-psa'
    subprocess.Popen(shlex.split(cmd), env=env)

    # start flower
    cmd = 'celery -A cwwed flower --port=5555'
    subprocess.Popen(shlex.split(cmd), env=env)


class Command(BaseCommand):

    def handle(self, *args, **options):
        autoreload.run_with_reloader(restart_celery)
