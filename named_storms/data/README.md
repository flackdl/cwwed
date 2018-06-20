# Covered Data

## JPL PODAAC - QuikSCAT Level 1C

[source](https://podaac.jpl.nasa.gov/dataset/QSCAT_L1C_NONSPINNING_SIGMA0_WINDS_V1?ids=Measurement:ProcessingLevel&values=Ocean%20Winds:*1*)

We're actually using version 2 even though version 1 is displayed on the main data access page.  The data is accessible as a thredds catalog and is in a binary format that can be consumed by numpy.  The dtype headers are included.  The timestamps start from 2000-01-01. The folders beneath the year, i.e "2018" are the day in the year, i.e "123" would be the 123rd day in that year.

