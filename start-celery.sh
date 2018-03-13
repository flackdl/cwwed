#!/usr/bin/env bash

PENV=/home/danny/.virtualenvs/cwwed-env/bin/

echo "starting celery workers"
${PENV}/celery -A cwwed worker -l info &

sleep 5

echo "staring celery flower"
${PENV}/celery flower -A cwwed --port=5555 &
