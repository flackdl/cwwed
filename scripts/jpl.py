import pandas
from datetime import datetime
import numpy as np

data_type = np.dtype([
    ('timestr', 'S21'), ('time', 'f8'), ('lon', 'f4'), ('lat', 'f4'),
    ('fp_start', 'i4'), ('fp_end', 'i4'), ('npts', 'i4'), ('s0', 'f4'),
    ('inc', 'f4'), ('azi', 'f4'), ('atten', 'f4'), ('beam', 'u1'),
    ('land', 'u1'), ('espd', 'f4'), ('edir', 'f4'), ('rspd', 'f4'),
])

data = np.fromfile('/home/danny/Downloads/QS_L1C_57676_V1.dat', dtype=data_type)

df = pandas.DataFrame(data)

print('Rows total: {}'.format(len(df.values)))

# TODO - instead, we should adjust the date we're comparing against to accommodate the year 2000 change
# TODO - this should solve the Series int error we were seeing
df = df[df['time'] > datetime(2018, 1, 1).timestamp()]
print('Rows after 2018-01-01: {}'.format(len(df.values)))
