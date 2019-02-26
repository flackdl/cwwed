#!/bin/bash

excluded_apps=(account sites auth admin sessions authtoken socialaccount contenttypes audit named_storms.namedstormcovereddatalog named_storms.nsem)

exclusions=''
for app in ${excluded_apps[*]}; do
    exclusions="${exclusions} --exclude ${app}"
done

python manage.py dumpdata --indent 2 ${exclusions}
