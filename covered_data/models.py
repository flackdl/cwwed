from django.contrib.gis.db import models


class NamedStorm(models.Model):
    name = models.CharField(max_length=50, unique=True)
    geo = models.GeometryField(geography=True, null=True)

    def __str__(self):
        return self.name


class CoveredDataProvider(models.Model):
    name = models.CharField(max_length=500)
    source = models.TextField()

    def __str__(self):
        return self.name


class CoveredData(models.Model):
    name = models.CharField(max_length=500, unique=True)
    named_storm = models.ForeignKey(NamedStorm, on_delete=models.CASCADE)
    providers = models.ManyToManyField(CoveredDataProvider)

    def __str__(self):
        return '({}) {}'.format(self.named_storm, self.name)
