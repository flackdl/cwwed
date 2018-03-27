import os
import shutil
from datetime import datetime
from django.conf import settings
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.http import FileResponse
from rest_framework import viewsets, exceptions
from rest_framework.decorators import detail_route
from rest_framework.parsers import FileUploadParser
from rest_framework.response import Response
from rest_framework import status
from named_storms.api.permissions import NSEMDjangoModelPermissions
from named_storms.models import NamedStorm, CoveredData, NSEM
from named_storms.api.serializers import NamedStormSerializer, CoveredDataSerializer, NamedStormDetailSerializer, NSEMSerializer
from named_storms.utils import named_storm_nsem_version_path


class NamedStormViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NamedStorm.objects.all()
    serializer_class = NamedStormSerializer
    filter_fields = ('name',)
    search_fields = ('name',)

    def get_serializer_class(self):
        # return a more detailed representation for a specific storm
        if self.action == 'retrieve':
            return NamedStormDetailSerializer
        return super().get_serializer_class()


class CoveredDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CoveredData.objects.all()
    serializer_class = CoveredDataSerializer


class NSEMViewset(viewsets.ModelViewSet):
    """
    Named Storm Event Model Viewset
    """
    queryset = NSEM.objects.all()
    serializer_class = NSEMSerializer

    @detail_route(url_path='(?P<filename>upload-output)', methods=['put'], parser_classes=(FileUploadParser,))
    def upload_output(self, *args, **kwargs):
        tmp_file = self.request.data['file']  # type: TemporaryUploadedFile
        instance = self.get_object()  # type: NSEM
        path = os.path.join(named_storm_nsem_version_path(instance), 'output.tgz')
        # move tmp file to nsem versioned path
        shutil.move(tmp_file.temporary_file_path(), path)
        # update the instance and save
        instance.model_output_snapshot = path
        instance.date_returned = datetime.utcnow()
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @detail_route(url_path='covered-data', methods=['get'], permission_classes=(NSEMDjangoModelPermissions,))
    def covered_data(self, *args, **kwargs):
        """
        Returns the actual covered data archive as a streamed file response
        """
        instance = self.get_object()  # type: NSEM

        # handle absent archive
        if not instance.covered_data_snapshot or not os.path.exists(instance.covered_data_snapshot):
            raise exceptions.NotFound

        # create the response
        response = FileResponse(
            open(instance.covered_data_snapshot, 'rb'),
            content_type=settings.CWWED_NSEM_ARCHIVE_CONTENT_TYPE)

        # include a helpful filename header
        response['Content-Disposition'] = 'attachment; filename="{}_covered-data_v{}.{}"'.format(
            instance.named_storm,
            instance.id,
            settings.CWWED_NSEM_ARCHIVE_EXTENSION,
        )

        return response
