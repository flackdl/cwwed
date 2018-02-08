from django.urls import path
from covered_data import views

urlpatterns = [
    path('latest/<int:storm_id>', views.latest)
]
