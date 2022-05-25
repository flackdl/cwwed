from django.contrib.gis import geos
from django.db import connection
from datetime import datetime
from named_storms.models import NsemPsaVariable


def wind_barbs_query(storm_name: str, psa_id: int, date: datetime, center: geos.Point, step=10, wind_speed_variable=NsemPsaVariable.VARIABLE_DATASET_WIND_SPEED):

    with connection.cursor() as cursor:
        sql = '''
            SELECT
               ST_AsText(d1.point),
               d1.value AS direction,
               d2.value AS speed
            FROM named_storms_nsempsadata d1
                INNER JOIN named_storms_nsempsavariable v1 ON (
                    v1.nsem_id = %(psa_id)s AND
                    v1.name = %(wind_direction)s AND
                    d1.date = %(date)s AND
                    d1.nsem_psa_variable_id = v1.id AND
                    d1.storm_name = %(storm_name)s
                )
                INNER JOIN named_storms_nsempsadata d2 ON (
                    d1.point = d2.point AND
                    d2.date = %(date)s AND
                    d1.id != d2.id
                )
                INNER JOIN named_storms_nsempsavariable v2 ON (
                    v2.nsem_id = %(psa_id)s AND
                    d2.nsem_psa_variable_id = v2.id AND
                    v2.name = %(wind_speed)s AND
                    d2.storm_name = %(storm_name)s
                )
                INNER JOIN named_storms_nsempsa nsn ON nsn.id = v1.nsem_id
                INNER JOIN named_storms_namedstorm n ON n.id = nsn.named_storm_id
            WHERE
                 ST_Within(d1.point::geometry, ST_Expand(ST_GeomFromText(%(center)s, 4326), %(expand_distance)s)) AND
                 d1.id %% %(step)s = 0
        '''

        params = {
            'storm_name': storm_name,
            'psa_id': psa_id,
            'date': date,
            'wind_direction': NsemPsaVariable.VARIABLE_DATASET_WIND_DIRECTION,
            'wind_speed': wind_speed_variable,
            'step': step,
            'center': center.wkt,
            # show more spatial distance of wind barbs when zoomed out
            'expand_distance': .2 if step == 1 else .8,
        }

        cursor.execute(sql, params)

        return cursor.fetchall()
