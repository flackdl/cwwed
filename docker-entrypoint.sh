#!/usr/bin/env bash

# migrate django database
python manage.py migrate

# run application
gunicorn --worker-class gthread --workers 4 --threads 4 --bind 0.0.0.0:80 cwwed.wsgi
