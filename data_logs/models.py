from django.contrib.gis.db import models
from named_storms.models import CoveredDataProvider, NamedStorm, CoveredData


class NamedStormCoveredDataLog(models.Model):
    named_storm = models.ForeignKey(NamedStorm, on_delete=models.CASCADE)
    covered_data = models.ForeignKey(CoveredData, on_delete=models.CASCADE)
    provider = models.ForeignKey(CoveredDataProvider, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)
    snapshot = models.TextField(blank=True)
    exception = models.TextField(blank=True)

    def __str__(self):
        if self.success:
            return self.snapshot
        return 'Error: {} // {}'.format(self.named_storm, self.covered_data)
