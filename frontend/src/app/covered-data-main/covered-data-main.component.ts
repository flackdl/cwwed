import { forkJoin } from 'rxjs';
import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from "@angular/router";
import { CwwedService } from "../cwwed.service";
import * as _ from 'lodash';

@Component({
  selector: 'app-covered-data-main',
  templateUrl: './covered-data-main.component.html',
  styleUrls: ['./covered-data-main.component.css']
})
export class CoveredDataMainComponent implements OnInit {
  coveredDataId: number;
  coveredDataList: any;

  constructor(
    private route: ActivatedRoute,
    private cwwedService: CwwedService,
    ) {}

   public activeCoveredData() {
    return _.find(this.cwwedService.coveredDataList, (data) => {
      return data.id == this.coveredDataId;
    });
   }

  ngOnInit() {
    this.coveredDataList = this.cwwedService.coveredDataList;

    this.route.params.subscribe((data) => {
      if (data.id) {
        this.coveredDataId = parseInt(data.id);
      }
    });
  }
}
