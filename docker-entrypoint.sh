#!/usr/bin/env bash

# migrate django database
python manage.py migrate

# create cache tables
python manage.py createcachetable

# run application
gunicorn --bind 0.0.0.0:80 cwwed.wsgi
