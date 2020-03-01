#!/usr/bin/env bash

# migrate django database
python manage.py migrate

# create cache tables
python manage.py createcachetable

# run application
gunicorn cwwed.wsgi --worker-class gthread --workers 4 --threads 4 --bind 0.0.0.0:80 --access-logfile -
