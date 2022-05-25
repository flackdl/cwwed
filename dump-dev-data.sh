#!/bin/bash


python manage.py dumpdata --indent 2 \
    named_storms.namedstorm \
    named_storms.covereddata \
    named_storms.covereddataprovider \
    named_storms.namedstormcovereddata \
    coastal_act.coastalactproject
