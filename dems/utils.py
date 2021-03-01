from django.conf import settings
from django.contrib.auth.models import Group


def get_dem_user_emails() -> list:
    dem_group = Group.objects.get(name=settings.CWWED_DEM_GROUP)
    return list(dem_group.user_set.values_list('email', flat=True))
