from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework import routers
from rest_framework.schemas import get_schema_view
from named_storms.api import urls as named_storms_urls
from coastal_act.api import urls as coastal_act_urls
from rest_framework.authtoken import views as drf_views

router = routers.DefaultRouter()

# extend router to include app's routers
router.registry.extend(named_storms_urls.router.registry)
router.registry.extend(coastal_act_urls.router.registry)


urlpatterns = [
    path('', include(router.urls)),
    path('docs/', TemplateView.as_view(
        template_name='api-docs.html',
        extra_context={'schema_url': 'openapi-schema'}
    ), name='api-docs'),
    path('openapi/', get_schema_view(
        title="CWWED",
        description="API for the Coastal Wind and Water Event Database",
        version="1.0.0",
    ), name='openapi-schema'),
    path('auth/', drf_views.obtain_auth_token),  # authenticates user and returns token
    *named_storms_urls.urlpatterns,
    *coastal_act_urls.urlpatterns,
]
