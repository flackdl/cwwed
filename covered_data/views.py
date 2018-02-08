import logging
from django.http import JsonResponse


def latest(request, storm_id):
    return JsonResponse({'hiya': 'there'})
