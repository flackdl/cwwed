from urllib.parse import quote
from revproxy.views import ProxyView, QUOTE_SAFE


class ThreddsProxy(ProxyView):

    def get_quoted_path(self, path):
        # overridden to use `quote` vs `quote_plus` because THREDDS was choking on the plus characters
        return quote(path.encode('utf8'), QUOTE_SAFE)
