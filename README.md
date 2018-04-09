# Coastal Wind and Water Event Database (CWWED)

https://www.weather.gov/sti/coastalact_cwwed

## Development & Initial Setup

Python environment (>=3.6)

    # create the environment
    mkvirtualenv cwwed-env
    
    # install requirements
    pip install -r requirements.txt
    
    # activate environment (if not already done)
    workon cwwed-env
    
Initial Setup

    # migrate/create tables
    python manage.py migrate
    
    # create super user
    python manage.py createsuperuser
    
    # load dev data
    python manage.py loaddata dev-db.json

    # create "nsem" user & model permissions
    python manage.py cwwed-init
   
Start PostGIS/THREDDS/RabbitMQ

    docker-compose up
    
Start Celery and Flower

    python manage.py celery
    
#### Helpers

Purge RabbitMQ

    docker-compose exec rabbitmq rabbitmqctl purge_queue celery
    
Purge Celery

    celery -A cwwed purge
    
    
#### NSEM process

Submit a new NSEM request using the user's generated token:

    curl -H "Authorization: Token aca89a70c8fa67144109b368b2b9994241bdbf2c" -H "Content-Type: application/json" -d '{"named_storm": "1"}' http://127.0.0.1:8000/api/nsem/
    
    {
        "id": 45,
        "covered_data_snapshot_url": "http://127.0.0.1:8000/api/nsem/43/covered-data/",
        "date_requested": "2018-04-04T14:28:00.646771Z",
        "date_returned": null,
        "covered_data_snapshot": "/media/bucket/cwwed/Harvey/NSEM/v43/input.tar",
        "model_output_snapshot": "",
        "named_storm": 1
    }

    
Download the covered data for an NSEM record:

    curl -s -H "Authorization: Token aca89a70c8fa67144109b368b2b9994241bdbf2c" http://127.0.0.1:8000/api/nsem/45/covered-data/ > /tmp/data.tgz
    
Upload model output for a specific NSEM record:

*NOTE: The input format must be tar+gzipped, i.e "output.tgz".*

    # assumes "output.tgz" is in current directory
    curl -XPUT -H "Authorization: Token aca89a70c8fa67144109b368b2b9994241bdbf2c" --data-binary @output.tgz "http://127.0.0.1:8000/api/nsem/45/upload-output/"
    
## Production *-TODO-*
Setup RDS with proper VPC and security group permissions.

EFS:
- Create EFS instance and configure `.ebextensions/storage-efs-mountfilesystem.config` with instance id.
- Assign EFS security group to EC2 instance(s).  (TODO - figure out how auto scaling default security groups work)

Environment variables
- DJANGO_SETTINGS_MODULE
- DATABASE_URL
- SLACK_BOT_TOKEN
- CWWED_NSEM_PASSWORD

Create S3 bucket and configure CORS settings (prepopulated settings look ok).
However, django-storages might configure it for us with `AWS_AUTO_CREATE_BUCKET`.

Elastic Beanstalk
    eb init
    eb create
    # set environment variables (incomplete example)
    eb setenv DJANGO_SETTINGS_MODULE=cwwed.settings-prod DATABASE_URL=postgis://XXXX:XXXX@XXXX:5432/XXXX
