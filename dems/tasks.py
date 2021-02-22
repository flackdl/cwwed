from cwwed.celery import app
from dems.models import DemSource
from dems.processor import DemSourceProcessor


@app.task()
def update_dems_task():
    for dem_source in DemSource.objects.all():
        processor = DemSourceProcessor(dem_source)
        processor.update()

