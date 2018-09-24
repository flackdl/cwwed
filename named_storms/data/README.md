# Covered Data

## USGS

https://stn.wim.usgs.gov/STNServices/Documentation/home

The STN Web Services provides a rest api to discover datasets.  There are many file types included in the output and therefore no filtering is done.


## NDBC

#### Standard Meteorological Data

https://dods.ndbc.noaa.gov/

THREDDS catalog with standard netcdf data.  Each sub catalog is for a different buoy.
 
## Jet Propulsion Labs

JPL offers a THREDDS catalog which we use for discovering the datasets.  
The catalogs are broken down initially by the year (i.e 2018) and then the day of the year (i.e "56" where it's the 56th day of the year).

#### JPL - QuikSCAT Level 1C

https://podaac.jpl.nasa.gov/dataset/QSCAT_L1C_NONSPINNING_SIGMA0_WINDS_V1?ids=Measurement:ProcessingLevel&values=Ocean%20Winds:*1*

ftp://podaac.jpl.nasa.gov/allData/quikscat/L1B/v2/docs/L1B_SIS_200609.pdf

The data is in a binary format that can be consumed by numpy.
The dtype headers are included.  The timestamps start from 2000-01-01.
We're actually using version 2 even though version 1 is displayed on the main data access page.  

#### JPL SMAP Level 2B

https://podaac.jpl.nasa.gov/dataset/SMAP_JPL_L2B_SSS_CAP_V4?ids=Measurement:ProcessingLevel&values=Ocean%20Winds:*2*

ftp://podaac-ftp.jpl.nasa.gov/allData/smap/docs/JPL-CAP_V4/JPL_SMAP-SSS-UsersGuide_V4.pdf

The data is in [Hierarchical Data Format](https://en.wikipedia.org/wiki/Hierarchical_Data_Format).
We're not filtering the dataset down via time/lon/lat because the data structure is in an unconventional grid and the sizes of the whole bundle isn't that large (<1GB).


#### JPL MetOp-A/B ASCAT L2

https://podaac.jpl.nasa.gov/dataset/ASCATA-L2-Coastal?ids=Measurement:Sensor&values=Ocean%20Winds:ASCAT

https://podaac.jpl.nasa.gov/dataset/ASCATB-L2-Coastal?ids=Measurement:Sensor&values=Ocean%20Winds:ASCAT

http://projects.knmi.nl/scatterometer/publications/pdf/ASCAT_Product_Manual.pdf

The data is netcdf, however, the dimensions aren't "standard" (ie. time, lat, lon).
Instead, the dimensions are "NUMROWS" and "NUMCELLS" which makes generic filtering challenging so we're currently just not doing it.
The file sizes aren't terribly big so we can address this later by defining a custom processor.

#### National Land Coverage Database

Provided by the Multi-Resolution Land Characteristics (MRLC).

https://www.mrlc.gov/nlcd2011.php

[File download](https://landfire.cr.usgs.gov/MRLC/NLCD/nlcd_2011_landcover_2011_edition_2014_10_10.zip?ORIG=137_singlelfr&SIZEMB=17881)

The data is a large zip file containing a few different image formats.  No data sub-setting is being performed.


#### CO-OPS

Center for Operational Oceanographic Products and Services

Data is provided through a REST API.

https://tidesandcurrents.noaa.gov/

https://tidesandcurrents.noaa.gov/api/

We're collecting the following products:
- Water Levels
- Air temperature
- Air pressure
- Wind

#### National Weather Model

The data lives on an FTP server.

http://water.noaa.gov/about/nwm

ftp://ftpprd.ncep.noaa.gov/pub/data/nccf/com/nwm/prod/

*NOTE - they're not configured to serve CWWED with historical data yet, so we're temporarily just collecting recent data*
