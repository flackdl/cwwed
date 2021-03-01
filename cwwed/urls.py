"""cwwed URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf.urls.static import static
from rest_framework.schemas import get_schema_view
from ratelimit.decorators import ratelimit

from cwwed.views import AngularStaticAssetsRedirectView
from audit.proxy import OpenDapProxy


urlpatterns = [
    path('', TemplateView.as_view(template_name='coastal_act/index.html'), name='home'),
    # rate limit the admin login
    path('admin/login/', ratelimit(key='ip', rate='5/m', method=['POST'], block=True)(admin.site.login)),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    re_path(r'^invitations/', include('invitations.urls', namespace='invitations')),
    re_path(r'^assets/', AngularStaticAssetsRedirectView.as_view()),  # static assets redirect for angular
    re_path(r'^opendap/(?P<path>.*)$', OpenDapProxy.as_view(upstream=settings.OPENDAP_URL)),

    # api
    path('api-auth/', include('rest_framework.urls')),
    path('api/', include('cwwed.api.urls')),
    path('openapi/', get_schema_view(
        title="CWWED",
        description="API for the Coastal Wind and Water Event Database",
        version="1.0.0",
    ), name='openapi-schema'),

]

# serving media in dev only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
