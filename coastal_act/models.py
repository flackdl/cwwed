from django.db import models


class CoastalActProject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    image_url = models.ImageField()
    description = models.TextField()

    def __str__(self):
        return self.name
