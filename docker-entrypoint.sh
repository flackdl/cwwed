#!/usr/bin/env bash

# migrate django database
python manage.py migrate

# create cache tables
python manage.py createcachetable

# run application
gunicorn cwwed.wsgi --worker-class gthread --workers 4 --threads 4 --bind 127.0.0.1:80 --bind [::1]:80
