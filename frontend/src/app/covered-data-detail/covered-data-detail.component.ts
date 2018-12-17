import { ActivatedRoute } from "@angular/router";
import { Component, OnInit, Input } from '@angular/core';
import { CwwedService } from "../cwwed.service";
import * as _ from 'lodash';


@Component({
  selector: 'app-covered-data-detail',
  templateUrl: './covered-data-detail.component.html',
  styleUrls: ['./covered-data-detail.component.css']
})
export class CoveredDataDetailComponent implements OnInit {
  public data: any;
  public namedStorms: any;
  public nsemList: any;

  constructor(
    private cwwedService: CwwedService,
    private route: ActivatedRoute,
  ) {}

  ngOnInit() {
    this.namedStorms = this.cwwedService.namedStorms;
    this.nsemList = this.cwwedService.nsemList;

    this.route.params.subscribe((params) => {
      this.data = _.find(this.cwwedService.coveredDataList, (data) => {
        return data.id == params.id;
      });
    });
  }

  public stormCoveredDataUrl(storm) {
    let foundNsem = _.find(this.nsemList, (nsem) => {
      return nsem.named_storm === storm.id;
    });
    if (foundNsem && (this.data.id in foundNsem.opendap_url_covered_data)) {
      return foundNsem.opendap_url_covered_data[this.data.id];
    }
    return '';
  }
}
