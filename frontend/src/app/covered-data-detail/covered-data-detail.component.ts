import { Component, OnInit, Input } from '@angular/core';
import { CwwedService } from "../cwwed.service";
import * as _ from 'lodash';


@Component({
  selector: 'app-covered-data-detail',
  templateUrl: './covered-data-detail.component.html',
  styleUrls: ['./covered-data-detail.component.css']
})
export class CoveredDataDetailComponent implements OnInit {
  @Input() data: any;
  public namedStorms: any;
  public nsemList: any;
  public stormNSEM: any = {};

  constructor(
    private cwwedService: CwwedService,
  ) {}

  ngOnInit() {
    this.namedStorms = this.cwwedService.namedStorms;
    this.nsemList = this.cwwedService.nsemList;
    _.each(this.namedStorms, (storm) => {
      let nsem = _.find(this.nsemList, (nsem) => {
        return nsem.named_storm === storm.id;
      });
      if (nsem) {
        this.stormNSEM[storm.id] = nsem;
      }
    });
  }

  public stormCoveredDataUrl(storm) {
    if (storm.id in this.stormNSEM) {
      return this.stormNSEM[storm.id].thredds_url_covered_data;
    }
    return '';
  }
}
