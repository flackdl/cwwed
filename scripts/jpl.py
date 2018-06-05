import os
from datetime import datetime
import numpy

DATE_EPOCH = datetime(2000, 1, 1)
#DATE_CMP = datetime(2019, 1, 1)
#DATE_CMP_TIMESTAMP = DATE_CMP.timestamp() - DATE_EPOCH.timestamp()
BASE_DIR = '/home/danny/Desktop/v1/'

# ftp://podaac.jpl.nasa.gov/allData/quikscat/L1C/sw/Python/quikscat_l1c.py
data_type = numpy.dtype([
    ('timestr', 'S21'), ('time', 'f8'), ('lon', 'f4'), ('lat', 'f4'),
    ('fp_start', 'i4'), ('fp_end', 'i4'), ('npts', 'i4'), ('s0', 'f4'),
    ('inc', 'f4'), ('azi', 'f4'), ('atten', 'f4'), ('beam', 'u1'),
    ('land', 'u1'), ('espd', 'f4'), ('edir', 'f4'), ('rspd', 'f4'),
    ('rdir', 'f4')])

min_date = None
max_date = None

for file in os.listdir(BASE_DIR):
    if file.endswith('.dat'):
        data = numpy.fromfile(os.path.join(BASE_DIR, file), dtype=data_type)
        file_min_date = datetime.fromtimestamp(data['time'].min() + DATE_EPOCH.timestamp())
        file_max_date = datetime.fromtimestamp(data['time'].max() + DATE_EPOCH.timestamp())

        if min_date is None or file_min_date < min_date:
            min_date = file_min_date

        if max_date is None or file_max_date > max_date:
            max_date = file_max_date

        print('File: {}'.format(file))
        print('File Min Stamp: {}'.format(data['time'].min()))
        print('File Max Stamp: {}'.format(data['time'].max()))
        print('File Min Date: {}'.format(file_min_date.isoformat()))
        print('File Max Date: {}'.format(file_max_date.isoformat()))

print('=====================')

print('Min Date: {}'.format(min_date.isoformat()))
print('Max Date: {}'.format(max_date.isoformat()))

#print('Rows total: {}'.format(len(data)))
#print('Rows filtered: {}'.format(len(data[data['time'] >= DATE_CMP_TIMESTAMP])))
