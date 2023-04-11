# Development

CWWED is built with the following:


| Name        | Description | Link
| ----------- | ----------- | -----------
| Cloud Provider | Amazon Web Services (AWS) | https://aws.amazon.com/
| Servers | Amazon Elastic Compute Cloud (EC2) | https://aws.amazon.com/ec2/
| Load Balancing | Amazon Elastic Load Balancing (ELB) | https://aws.amazon.com/elasticloadbalancing/
| Auto Scaling | AWS Auto Scaling  | https://aws.amazon.com/autoscaling/
| File Storage | Amazon Elastic File System (EFS) | https://aws.amazon.com/efs/
| Object Storage | Amazon Simple Storage Service (S3) | https://aws.amazon.com/s3/
| Cold Storage | Amazon S3 Glacier | https://aws.amazon.com/glacier/
| Relational Database | Amazon Relational Database Service (RDS + PostgreSQL) | https://aws.amazon.com/rds/
| Server Orchestration | Kubernetes | https://kubernetes.io/
| Version Control | GitHub | http://github.com
| Server programming Language | Python | https://www.python.org/
| Client programming Language | Typescript / Javascript | https://www.typescriptlang.org/
| Server Web Framework | Django | https://www.djangoproject.com/
| Client Web Framework | Angular | https://angular.io/
| Client CSS Framework | Bootstrap | https://getbootstrap.com/
| Distributed Task Queue | Celery | http://www.celeryproject.org/
| GIS backend | GEOS | https://docs.djangoproject.com/en/3.1/ref/contrib/gis/geos/
| GIS frontend | OpenLayers | https://openlayers.org


### Python Environment (>=3.6)

Create the python environment:

    python3 -mvenv ~/.envs/cwwed-env

Activate the environment:

    . ~/.envs/cwwed-env
    
Install requirements:

    pip install -r requirements.txt

### Running services via Docker Compose

CWWED requires PostGIS, OPeNDAP, and Redis which can be run via Docker:

    docker-compose up -d

### Initial Setup

Migrate/create db tables:

    python manage.py migrate

Create superuser:

    python manage.py createsuperuser

Load dev data:

    python manage.py loaddata dev-db.json

Initialize:

*NOTE* you'll need the env variable `CWWED_NSEM_PASSWORD` defined before running, something like:

    CWWED_NSEM_PASSWORD=abc123 python manage.py cwwed-init

Create data folder `/media/bucket/cwwed/`:

    sudo mkdir -p /media/bucket/cwwed/
    sudo chown -R $USER:$USER /media/bucket/cwwed/

### Run front-end app

Build front-end app and watch for changes:

    npm --prefix frontend run watch

### Run back-end app

Start django server and watch for changes:

    python manage.py runserver

The server will now be running on http://localhost:8000.
    
Start Celery task queue and Flower (celery web management):

    python manage.py celery

*Celery will automatically restart during code changes.*
    
### Collect Covered Data

All data:

    python manage.py collect_covered_data

Specific storm:

    python manage.py collect_covered_data --storm_id 2

## Helpers

Purge Celery:

    celery -A cwwed purge -f

Purge REDIS:

    docker-compose exec redis redis-cli FLUSHALL   

Dump Postgres table(s):

    # local: data only, specific tables
    docker-compose exec postgis pg_dump -a -h localhost -U postgres -d postgres -t named_storms_nsempsavariable -t named_storms_nsempsadata > ~/Desktop/cwwed.sql

Connect to remote Postgres:

    docker-compose exec postgis psql -h XXX.rds.amazonaws.com -U XXX cwwed_dev
    
    
