from django.conf import settings
from django.views.generic.base import RedirectView


class AngularStaticAssetsRedirectView(RedirectView):
    """
    Redirect angular assets requests to something like "/static/angular/assets/" (settings.STATIC_ANGULAR_ASSETS_URL) since
    they're built to django's static directory
    """

    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        url = '{}{}'.format(settings.STATIC_ANGULAR_ASSETS_URL, self.request.path.lstrip('/'))
        return url
