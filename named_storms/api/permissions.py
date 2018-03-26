from rest_framework.permissions import DjangoModelPermissions


class NSEMDataPermission(DjangoModelPermissions):
    """
    Requires the user have "add" model permission (even though they may just get downloading via GET)
    """
    def __init__(self):
        self.perms_map = {
            'GET': self.perms_map['POST'],
        }
