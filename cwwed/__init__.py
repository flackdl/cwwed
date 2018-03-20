from __future__ import absolute_import, unicode_literals

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celery import app as celery_app

from cwwed import settings
from slacker import Slacker

# slack instance
slack = Slacker(settings.SLACK_BOT_TOKEN)

__all__ = ['celery_app', 'slack']
