from rest_framework.response import Response
from rest_framework import views
from named_storms.models import NsemPsaVariable


class PsaOptions(views.APIView):
    def get(self, request):
        return Response({
            'variables': NsemPsaVariable.VARIABLES,
        })
