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

Create "nsem" user in django admin and grant model permissions "add" and "change".

Submit a new NSEM request using the user's generated token:

    curl -H "Authorization: Token 1d3420aed1622ee5aa0e4c1663279c7a1014cbf8" -H "Content-Type: application/json" -d '{"named_storm": "1"}' http://127.0.0.1:8000/api/nsem/
    
Download the covered data for an NSEM record:

    curl http://127.0.0.1:8000/api/nsem/28/covered-data/ > /tmp/data.tgz
    
## Production

Define environment variables
- SLACK_BOT_TOKEN (app & celery)
