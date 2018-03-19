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
    
   
## Production

Define environment variables
- SLACK_BOT_KEY 
