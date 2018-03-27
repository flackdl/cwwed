# Coastal Wind and Water Event Database (CWWED)

https://www.weather.gov/sti/coastalact_cwwed

## Development

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
    
    
#### NSEM process

Create "nsem" user in django admin and grant model permissions "add", "change" and custom download permission:

    python manage.py cwwed-init

Submit a new NSEM request using the user's generated token:

    curl -H "Authorization: Token 32d7c8e358dda87b16e400f90a74ea55dac72fa8" -H "Content-Type: application/json" -d '{"named_storm": "1"}' http://127.0.0.1:8000/api/nsem/
    
    {
        "date_requested": "2018-03-27T13:51:07.227923Z",
        "date_returned": null,
        "id": 35,
        "model_input": "/media/bucket/cwwed/Harvey/NSEM/v35/input.tgz",
        "model_output": "",
        "named_storm": 1
    }

    
Download the covered data for an NSEM record:

    curl -H "Authorization: Token 32d7c8e358dda87b16e400f90a74ea55dac72fa8" http://127.0.0.1:8000/api/nsem/35/covered-data/ > /tmp/data.tgz
    
Upload model output for a specific NSEM record:

    # assumes "output.tgz" is in current directory
    curl -XPUT -H "Authorization: Token 32d7c8e358dda87b16e400f90a74ea55dac72fa8" --data-binary @output.tgz "http://127.0.0.1:8000/api/nsem/35/upload-output/"
    
## Production

Define environment variables
- SLACK_BOT_TOKEN (app & celery)
- CWWED_NSEM_PASSWORD