#!/usr/bin/env bash

# migrate django database
python manage.py migrate

# run application
gunicorn --worker-class gthread --workers 2 --threads 2 --bind 0.0.0.0:80 cwwed.wsgi
