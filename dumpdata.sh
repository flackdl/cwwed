#!/bin/bash
apps=(audit auth admin sessions authtoken socialaccount)
exclusions=''
for app in ${apps[*]}; do
    exclusions="${exclusions} --exclude ${app}"
done
python manage.py dumpdata --indent 1 ${exclusions}
