from django.conf import settings
from django.contrib.auth.models import User, Permission
from django.core.management import BaseCommand

from named_storms.models import NSEM


class Command(BaseCommand):
    help = 'CWWED Init'

    def handle(self, *args, **options):
        self._create_nsem_user()

    @staticmethod
    def _create_nsem_user():
        """
        create nsem user and assign permissions
        """
        users = User.objects.filter(username=settings.CWWED_NSEM_USER)
        if users.exists():
            user = users[0]
        else:
            user = User.objects.create_user(settings.CWWED_NSEM_USER, password=settings.CWWED_NSEM_PASSWORD)
        perm_names = [
            'change_{}'.format(NSEM._meta.model_name),  # change model
            'add_{}'.format(NSEM._meta.model_name),  # add model
            settings.CWWED_NSEM_PERMISSION_DOWNLOAD_DATA,  # custom download permission
        ]
        perms = Permission.objects.filter(codename__in=perm_names)
        user.user_permissions.set([p for p in perms])  # iterate because it won't accept a Queryset
