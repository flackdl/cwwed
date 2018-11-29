from django.contrib.auth.models import User
from django.contrib.gis.db import models


class OpenDapRequestLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date_requested = models.DateTimeField(auto_now_add=True)
    path = models.TextField()

    def __str__(self):
        return self.path
