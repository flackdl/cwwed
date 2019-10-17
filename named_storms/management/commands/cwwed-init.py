from django.conf import settings
from django.contrib.auth.models import User, Permission
from django.core.management import BaseCommand
from named_storms.models import NsemPsa, NamedStormCoveredDataSnapshot


class Command(BaseCommand):
    help = 'CWWED Init'

    def handle(self, *args, **options):
        if not settings.CWWED_NSEM_PASSWORD:
            raise RuntimeError('CWWED_NSEM_PASSWORD needs to be defined')
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
            'add_{}'.format(NsemPsa._meta.model_name),
            'add_{}'.format(NamedStormCoveredDataSnapshot._meta.model_name),
        ]
        perms = Permission.objects.filter(codename__in=perm_names)
        user.user_permissions.set([p for p in perms])  # iterate because it won't accept a Queryset
