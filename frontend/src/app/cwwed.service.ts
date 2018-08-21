import { HttpClient } from "@angular/common/http";
import { Injectable } from '@angular/core';
import { map } from 'rxjs/operators';
import { environment } from '../environments/environment';

let API_ROOT_DEV = 'http://localhost:8000/api';
let API_ROOT_PROD = 'http://dev.cwwed-staging.com/api';
let API_ROOT = environment.production ? API_ROOT_PROD : API_ROOT_DEV;
let API_COVERED_DATA = `${API_ROOT}/covered-data/`;

@Injectable({
  providedIn: 'root'
})
export class CwwedService {
  coveredDataList: any = [];

  constructor(
    private http: HttpClient,
  ) {}

  public fetchCoveredData() {
    return this.http.get(API_COVERED_DATA).pipe(
      map((data) => {
        this.coveredDataList = data;
        return this.coveredDataList;
      }),
    );
  }
}
