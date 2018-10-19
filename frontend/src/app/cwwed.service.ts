import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable } from '@angular/core';
import { map } from 'rxjs/operators';
import { environment } from '../environments/environment';

let API_ROOT_DEV = 'http://localhost:8000/api';
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
      map((data: any[]) => {
        if (data.length) {
            this.user = data[0];
            return this.user;
        }
      }),
    );
  }

  public fetchNamedStorms() {
    return this.http.get(API_NAMED_STORMS).pipe(
      map((data) => {
        this.namedStorms = data;
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
      map((data) => {
        this.coveredDataList = data;
        return this.coveredDataList;
      }),
    );
  }

  public fetchCoastalActProjects() {
    return this.http.get(API_COASTAL_ACT_PROJECTS).pipe(
      map((data) => {
        this.coastalActProjects = data;
        return this.coastalActProjects;
      }),
    );
  }
}
