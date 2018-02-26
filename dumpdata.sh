#!/bin/bash

excluded_apps=(sites auth admin sessions authtoken socialaccount contenttypes audit)

exclusions=''
for app in ${excluded_apps[*]}; do
    exclusions="${exclusions} --exclude ${app}"
done

python manage.py dumpdata --indent 1 ${exclusions}
