#!/usr/bin/env bash

# build/migrate django database
python manage.py migrate

# run application
gunicorn -w 4 -b 0.0.0.0:80 cwwed.wsgi
