import { HttpClient } from "@angular/common/http";
import { Injectable } from '@angular/core';

let API_ROOT = 'http://localhost:8000/api';
let API_COVERED_DATA = `${API_ROOT}/covered-data/`;

@Injectable({
  providedIn: 'root'
})
export class CwwedService {
  coveredDataList: any = [];

  constructor(
    private http: HttpClient,
  ) { }

  public fetchCoveredData() {

    // load covered data
    return this.http.get(API_COVERED_DATA).subscribe((data) => {
      this.coveredDataList = data;
    });

  }
}
