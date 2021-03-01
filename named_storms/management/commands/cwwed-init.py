from django.conf import settings
from django.contrib.auth.models import User, Permission, Group
from django.core.management import BaseCommand
from named_storms.models import NsemPsa, NamedStormCoveredDataSnapshot


class Command(BaseCommand):
    help = 'CWWED Init'

    def handle(self, *args, **options):
        if not settings.CWWED_NSEM_PASSWORD:
            raise RuntimeError('CWWED_NSEM_PASSWORD needs to be defined')
        self._create_nsem_user()
        self._create_dem_group()

    @staticmethod
    def _create_dem_group():
        """
        Create "dem" group
        """
        group, _ = Group.objects.get_or_create(name=settings.CWWED_DEM_GROUP)

    @staticmethod
    def _create_nsem_user():
        """
        Create nsem user & group and assign permissions
        """
        users = User.objects.filter(username=settings.CWWED_NSEM_USER)
        if users.exists():
            user = users[0]
        else:
            user = User.objects.create_user(settings.CWWED_NSEM_USER, password=settings.CWWED_NSEM_PASSWORD)
        group, _ = Group.objects.get_or_create(name=settings.CWWED_NSEM_GROUP)
        perm_names = [
            'add_{}'.format(NsemPsa._meta.model_name),
            'add_{}'.format(NamedStormCoveredDataSnapshot._meta.model_name),
        ]
        perms = Permission.objects.filter(codename__in=perm_names)
        # set permission
        user.user_permissions.set(list(perms))
        group.permissions.set(list(perms))
        # add user to group
        group.user_set.add(user)
