from celery import chain

from cwwed.celery import app
from dems.models import DemSource
from dems.processor import DemSourceProcessor


@app.task()
def update_dems():
    chain(
        # update dems from their sources
        update_dems_list_task.si(),
        # update individual dem raster meta data
        update_dems_data_task.si(),
    )()


@app.task()
def update_dems_list_task():
    for dem_source in DemSource.objects.all():
        processor = DemSourceProcessor(dem_source)
        processor.update_list()


@app.task()
def update_dems_data_task():
    for dem_source in DemSource.objects.all():
        processor = DemSourceProcessor(dem_source)
        for dem in dem_source.dem_set.all():
            processor.update_dem_data(dem)
