import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable } from '@angular/core';
import { map } from 'rxjs/operators';
import { environment } from '../environments/environment';

let API_ROOT_DEV = '/api';
let API_ROOT_PROD = 'https://dev.cwwed-staging.com/api';
let API_ROOT = environment.production ? API_ROOT_PROD : API_ROOT_DEV;
let API_USER = `${API_ROOT}/user/`;
let API_COVERED_DATA = `${API_ROOT}/covered-data/`;
let API_NAMED_STORMS = `${API_ROOT}/named-storms/`;
let API_NSEM_PER_STORM = `${API_ROOT}/nsem/per-storm/`;
let API_COASTAL_ACT_PROJECTS = `${API_ROOT}/coastal-act-projects/`;

@Injectable({
  providedIn: 'root'
})
export class CwwedService {
  user: any;
  coveredDataList: any;
  namedStorms: any;
  nsemList: any;
  coastalActProjects: any;

  constructor(
    private http: HttpClient,
  ) {}

  public fetchUser() {
    return this.http.get(API_USER).pipe(
      map((data: any) => {
        if (data.results.length) {
          this.user = data.results[0];
          return this.user;
        }
      }),
    );
  }

  public fetchNamedStorms() {
    return this.http.get(API_NAMED_STORMS).pipe(
      map((data: any) => {
        this.namedStorms = data.results;
        return this.namedStorms;
      }),
    );
  }

  public fetchNSEMPerStorm(params?) {
    params = params ? params : {};

    // build http params from supplied params
    let options = { params: new HttpParams() };
    for (let key in params) {
      options.params.set(key, params[key]);
    }

    return this.http.get(API_NSEM_PER_STORM, options).pipe(
      map((data) => {
        this.nsemList = data;
        return this.nsemList;
      }),
    );
  }

  public fetchCoveredData() {
    return this.http.get(API_COVERED_DATA).pipe(
      map((data: any) => {
        this.coveredDataList = data.results;
        return this.coveredDataList;
      }),
    );
  }

  public fetchCoastalActProjects() {
    return this.http.get(API_COASTAL_ACT_PROJECTS).pipe(
      map((data: any) => {
        this.coastalActProjects = data.results;
        return this.coastalActProjects;
      }),
    );
  }

  public fetchPSATimeSeriesData(namedStormId: number, lat: number, lon: number) {
    return this.http.get(`${API_NAMED_STORMS}${namedStormId}/psa/data/time-series/${lat}/${lon}`).pipe(
      map((data) => {
        return data;
      }),
    );
  }

  public fetchPSAVariables(namedStormId: number) {
    return this.http.get(`${API_NAMED_STORMS}${namedStormId}/psa/variable/`).pipe(
      map((data: any) => {
        return data.results;
      }),
    );
  }

  public fetchPSAVariablesDataDates(namedStormId: number) {
    return this.http.get(`${API_NAMED_STORMS}${namedStormId}/psa/data/dates/`).pipe(
      map((data) => {
        return data;
      }),
    );
  }

  public static getPsaVariableGeoUrl(named_storm_id: number, variableId: string, date?: string) {
    const params = {
      nsem_psa_variable: variableId,
      value__gt: '0',  // TODO - dataset should already be filtered?
    };
    if (date) {
      params['date'] = date;
    }
    const httpParams = new HttpParams({fromObject: params});
    return `${API_NAMED_STORMS}${named_storm_id}/psa/geojson/?${httpParams}`;
  }
}
