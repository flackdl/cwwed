#!/usr/bin/env bash

# migrate django database
python manage.py migrate

# create cache tables
python manage.py createcachetable

# run application on ipv4 and ipv6
gunicorn cwwed.wsgi --worker-class gthread --workers 2 --threads 2 --bind [::]:80
