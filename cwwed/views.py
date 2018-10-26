import os
import xarray as xr
from django.conf import settings
from django.http import HttpResponse, Http404, StreamingHttpResponse
from django.views.generic.base import RedirectView, View


class AngularStaticAssetsRedirectView(RedirectView):
    """
    Redirect angular assets requests to something like "/static/angular/assets/" (settings.STATIC_ANGULAR_ASSETS_URL) since
    they're built to django's static directory
    """

    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        url = '{}{}'.format(settings.STATIC_ANGULAR_ASSETS_URL, self.request.path.lstrip('/'))
        return url


class PSAFilterView(View):

    _dataset: xr.Dataset = None

    def get(self, request):
        path = request.GET.get('path')
        extent = request.GET.getlist('extent')
        if not path or not os.path.exists(path):
            raise Http404('Path does not exist')
        elif not extent or not len(extent) == 4:
            raise Http404('Extent bounds (4) not supplied')
        try:
            extent = list(map(float, extent))
        except ValueError:
            raise Http404('Extent bounds should be floats')

        lon_start = extent[0]
        lon_end = extent[2]
        lat_start = extent[1]
        lat_end = extent[3]

        self._dataset = xr.open_dataset(path)

        mask = (
                (self._dataset.nmesh2d_face.mesh2d_face_x >= lon_start)
                & (self._dataset.nmesh2d_face.mesh2d_face_x <= lon_end)
                & (self._dataset.nmesh2d_face.mesh2d_face_y >= lat_start)
                & (self._dataset.nmesh2d_face.mesh2d_face_y <= lat_end)
        )

        # TODO - apply mask to all relevant variables

        result = self._dataset.nmesh2d_face[mask]

        return HttpResponse(str(result), content_type='text/plain')

        # TODO - this reads the entire dataset into memory
        #response = HttpResponse(self._dataset.to_netcdf(), content_type='application/x-netcdf')
        #response['Content-Disposition'] = 'attachment; filename="data.nc"'
        #return response