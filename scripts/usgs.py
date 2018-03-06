import os
import re
import sys

import errno
import requests
from io import open

EVENT_ID_MATTHEW = 135  # default

# capture an event_id from the command line, defaulting to Matthew
EVENT_ID = sys.argv[1] if len(sys.argv) > 1 else EVENT_ID_MATTHEW

# file type "data"
# https://stn.wim.usgs.gov/STNServices/FileTypes.json
FILE_TYPE_DATA = 2

# deployment types
# https://stn.wim.usgs.gov/STNServices/DeploymentTypes.json
DEPLOYMENT_TYPE_WATER_LEVEL = 1
DEPLOYMENT_TYPE_WAVE_HEIGHT = 2
DEPLOYMENT_TYPE_BAROMETRIC = 3
DEPLOYMENT_TYPE_TEMPERATURE = 4
DEPLOYMENT_TYPE_WIND_SPEED = 5
DEPLOYMENT_TYPE_HUMIDITY = 6
DEPLOYMENT_TYPE_AIR_TEMPERATURE = 7
DEPLOYMENT_TYPE_WATER_TEMPERATURE = 8
DEPLOYMENT_TYPE_RAPID_DEPLOYMENT = 9

# create output directory
output_directory = 'output'
try:
    os.makedirs(output_directory)
except OSError as exception:
    if exception.errno != errno.EEXIST:
        raise

# fetch event data files
files_req = requests.get('https://stn.wim.usgs.gov/STNServices/Events/{}/Files.json'.format(EVENT_ID))
files_req.raise_for_status()
files_json = files_req.json()

# fetch event sensors
sensors_req = requests.get('https://stn.wim.usgs.gov/STNServices/Events/{}/Instruments.json'.format(EVENT_ID))
sensors_req.raise_for_status()
sensors_json = sensors_req.json()

# filter sensors down to barometric ones
barometric_sensors = [sensor for sensor in sensors_json if sensor.get('deployment_type_id') == DEPLOYMENT_TYPE_BAROMETRIC]

# print file urls for barometric sensors for this event
for file in files_json:
    if file['filetype_id'] == FILE_TYPE_DATA and file['instrument_id'] in [s['instrument_id'] for s in barometric_sensors]:

        file_url = 'https://stn.wim.usgs.gov/STNServices/Files/{}/item'.format(file['file_id'])

        # fetch the actual file
        file_req = requests.get(file_url, stream=True)

        # capture the filename from the headers so we can save it appropriately
        match = re.match('.*filename="(?P<filename>.*)"', file_req.headers['Content-Disposition'])
        if match:
            filename = match.group('filename')
        else:
            filename = '{}.unknown'.format(file['file_id'])
            print('COULD NOT FIND "filename" in header, saving as {}'.format(filename))

        print('{}\t\t({})'.format(filename, file_url))

        with open('{}/{}'.format(output_directory, filename), 'wb') as f:
            for chunk in file_req.iter_content(chunk_size=1024):
                f.write(chunk)
