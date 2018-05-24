import os
import shlex
import subprocess
from django.core.management.base import BaseCommand
from django.utils import autoreload


def restart_celery():
    # kill celery/flower
    cmd = 'pkill celery'
    subprocess.call(shlex.split(cmd))

    # include the current environment
    env = os.environ.copy()

    # start celery
    cmd = 'celery worker -A cwwed -l info'
    subprocess.Popen(shlex.split(cmd), env=env)

    # start flower
    cmd = 'celery flower -A cwwed --port=5555'
    subprocess.Popen(shlex.split(cmd), env=env)


class Command(BaseCommand):

    def handle(self, *args, **options):
        autoreload.main(restart_celery)
