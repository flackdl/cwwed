# Covered Data

## USGS

[source](https://stn.wim.usgs.gov/STNServices/Documentation/home)

The STN Web Services provides a rest api to discover datasets.  There are many file types included in the output and therefore no filtering is done.


## NDBC

#### Standard Meteorological Data

[source / documentation](https://dods.ndbc.noaa.gov/)

THREDDS catalog with standard netcdf data.  Each sub catalog is for a different buoy.
 
## Jet Propulsion Labs

JPL offers a THREDDS catalog which we use for discovering the datasets.  
The catalogs are broken down initially by the year (i.e 2018) and then the day of the year (i.e "56" where it's the 56th day of the year).

#### JPL - QuikSCAT Level 1C

[source](https://podaac.jpl.nasa.gov/dataset/QSCAT_L1C_NONSPINNING_SIGMA0_WINDS_V1?ids=Measurement:ProcessingLevel&values=Ocean%20Winds:*1*)
/
[documentation](ftp://podaac.jpl.nasa.gov/allData/quikscat/L1B/v2/docs/L1B_SIS_200609.pdf)

The data is in a binary format that can be consumed by numpy.
The dtype headers are included.  The timestamps start from 2000-01-01.
We're actually using version 2 even though version 1 is displayed on the main data access page.  

#### JPL SMAP Level 2B

[source](https://podaac.jpl.nasa.gov/dataset/SMAP_JPL_L2B_SSS_CAP_V4?ids=Measurement:ProcessingLevel&values=Ocean%20Winds:*2*)
/
[documentation](ftp://podaac-ftp.jpl.nasa.gov/allData/smap/docs/JPL-CAP_V4/JPL_SMAP-SSS-UsersGuide_V4.pdf)

The data is in [Hierarchical Data Format](https://en.wikipedia.org/wiki/Hierarchical_Data_Format).
We're not filtering the dataset down via time/lon/lat because the data structure is in an unconventional grid and the sizes of the whole bundle isn't that large (<1GB).


#### JPL MetOp-A ASCAT L2

[source](https://podaac.jpl.nasa.gov/dataset/ASCATA-L2-Coastal?ids=Measurement:Sensor&values=Ocean%20Winds:ASCAT)
/
[documentation](http://projects.knmi.nl/scatterometer/publications/pdf/ASCAT_Product_Manual.pdf)

The data is netcdf, however, the dimensions aren't "standard" (ie. time, lat, lon).
Instead, the dimensions are "NUMROWS" and "NUMCELLS" which makes generic filtering challenging so we're currently just not doing it.
The file sizes aren't terribly big so we can address this later by defining a custom processor.
