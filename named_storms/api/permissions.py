from django.conf import settings
from rest_framework.permissions import DjangoModelPermissions
from named_storms.models import NSEM


class NSEMDjangoModelPermissions(DjangoModelPermissions):
    """
    Requires the user to have the standard model permissions and a custom download permission
    """

    def has_permission(self, request, view):
        has_perm = super().has_permission(request, view)
        if not has_perm:
            return False
        custom_perm = '{}.{}'.format(NSEM._meta.app_label, settings.CWWED_NSEM_PERMISSION_DOWNLOAD_DATA)
        return request.user.has_perm(custom_perm)
