#!/usr/bin/env bash

# migrate django database
python manage.py migrate

# create cache tables
python manage.py createcachetable

# run cwwed init
python manage.py cwwed-init

# run application on ipv4 and ipv6
gunicorn cwwed.wsgi --max-requests 1000 --worker-class gthread --workers 4 --threads 4 --bind [::]:80
