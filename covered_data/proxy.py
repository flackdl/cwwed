from urllib.parse import quote
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from revproxy.views import ProxyView, QUOTE_SAFE


class ThreddsProxy(ProxyView):

    @method_decorator(login_required)
    def dispatch(self, request, path):
        return super().dispatch(request, path)

    def get_quoted_path(self, path):
        # overridden to use `quote` vs `quote_plus` because THREDDS was choking on the plus characters
        return quote(path.encode('utf8'), QUOTE_SAFE)
