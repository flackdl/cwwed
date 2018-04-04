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
   
Start PostGIS/THREDDS/RabbitMQ

    docker-compose up
    
Start Celery and Flower

    python manage.py celery
    
Initial Setup

    # migrate/create tables
    python manage.py migrate
    
    # create super user
    python manage.py createsuperuser
    
    # load dev data
    python manage.py loaddata dev-db.json

    # create "nsem" user & model permissions
    python manage.py cwwed-init
    
#### Helpers

Purge RabbitMQ

    docker-compose exec rabbitmq rabbitmqctl purge_queue celery
    
Purge Celery

    celery -A cwwed purge
    
    
#### NSEM process

Submit a new NSEM request using the user's generated token:

    curl -H "Authorization: Token 32d7c8e358dda87b16e400f90a74ea55dac72fa8" -H "Content-Type: application/json" -d '{"named_storm": "1"}' http://127.0.0.1:8000/api/nsem/
    
    {
        "id": 38,
        "covered_data_snapshot_url": "http://127.0.0.1:8000/api/nsem/43/covered-data/",
        "date_requested": "2018-04-04T14:28:00.646771Z",
        "date_returned": null,
        "covered_data_snapshot": "/media/bucket/cwwed/Harvey/NSEM/v43/input.tar",
        "model_output_snapshot": "",
        "named_storm": 1
    }

    
Download the covered data for an NSEM record:

    curl -s -H "Authorization: Token 32d7c8e358dda87b16e400f90a74ea55dac72fa8" http://127.0.0.1:8000/api/nsem/38/covered-data/ > /tmp/data.tgz
    
Upload model output for a specific NSEM record:

*NOTE: The input format must be tar+gzipped, i.e "output.tgz".*

    # assumes "output.tgz" is in current directory
    curl -XPUT -H "Authorization: Token 32d7c8e358dda87b16e400f90a74ea55dac72fa8" --data-binary @output.tgz "http://127.0.0.1:8000/api/nsem/38/upload-output/"
    
## Production

Define environment variables
- SLACK_BOT_TOKEN (app & celery)
- CWWED_NSEM_PASSWORD