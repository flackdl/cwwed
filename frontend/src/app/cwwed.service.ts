import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable } from '@angular/core';
import { map } from 'rxjs/operators';
import * as _ from "lodash";

let API_ROOT = '/api';
let API_USER = `${API_ROOT}/user/`;
let API_COVERED_DATA = `${API_ROOT}/covered-data/`;
let API_NAMED_STORMS = `${API_ROOT}/named-storm/`;
let API_NSEM_PSA_USER_EXPORT = `${API_ROOT}/nsem-psa-user-export/`;
let API_NSEM_PER_STORM = `${API_ROOT}/nsem-psa/per-storm/`;
let API_COASTAL_ACT_PROJECTS = `${API_ROOT}/coastal-act-project/`;

@Injectable({
  providedIn: 'root'
})
export class CwwedService {
  user: any;
  coveredDataList: any;
  namedStorms: any;
  nsemPsaList: any;
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
        this.nsemPsaList = data;
        return this.nsemPsaList;
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

  public getPSATimeSeriesDataURL(namedStormId: number, lat: number, lon: number) {
    return `${API_NAMED_STORMS}${namedStormId}/psa/data/time-series/${lat}/${lon}/`;
  }

  public fetchPSATimeSeriesData(namedStormId: number, lat: number, lon: number) {
    return this.http.get(this.getPSATimeSeriesDataURL(namedStormId, lat, lon)).pipe(
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

  public fetchPSAUserExport(id: number) {
    return this.http.get(`${API_NSEM_PSA_USER_EXPORT}${id}/`).pipe(
      map((data) => {
        return data;
      }),
    );
  }

  public createPsaUserExport(namedStormId: number, bbox: string, format: string, dateFilter?: string) {
    // fetch the psa for this storm to to the data
    const psa = _.find(this.nsemPsaList, (nsemPsa) => {
      return nsemPsa.named_storm === namedStormId;
    });
    const data = {
      bbox: bbox,
      format: format,
      nsem: psa.id,
    };
    if (dateFilter) {
      data['date_filter'] = dateFilter;
    }

    return this.http.post(`${API_NAMED_STORMS}${namedStormId}/psa/export/`, data).pipe(
      map((data) => {
        return data;
      }),
    );
  }

  //
  // static methods
  //

  public static getPsaVariableGeoUrl(namedStormId: number, variableName: string, date?: string) {
    const url = `${API_NAMED_STORMS}${namedStormId}/psa/contour/`;
    const params = {
      nsem_psa_variable: variableName,
    };
    if (date) {
      params['date'] = date;
    }
    const httpParams = new HttpParams({fromObject: params});
    return `${url}?${httpParams}`;
  }

  public static getPsaVariableWindBarbsUrl(namedStormId: number, variableName: string, date: string, center: string, step: number) {
    const httpParams = new HttpParams({fromObject: {
      'center': center,
      'step': String(step),
    }});
    return `${API_NAMED_STORMS}${namedStormId}/psa/data/wind-barbs/${date}/?${httpParams}`;
  }
}
