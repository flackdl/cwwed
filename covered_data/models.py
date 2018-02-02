from django.db import models


class NamedStorm(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class CoveredData(models.Model):
    named_storm = models.ForeignKey(NamedStorm, on_delete=models.CASCADE)
    name = models.CharField(max_length=500, unique=True)

    def __str__(self):
        return '({}) {}'.format(self.named_storm, self.name)


class CoveredDataProvider(models.Model):
    covered_data = models.ForeignKey(CoveredData, on_delete=models.CASCADE)
    name = models.CharField(max_length=500)
    source = models.TextField()
    output = models.TextField(blank=True)

    def __str__(self):
        return '({}) {}'.format(self.name, self.covered_data)
