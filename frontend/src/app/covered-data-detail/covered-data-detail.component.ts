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

  constructor(
    private cwwedService: CwwedService,
  ) {}

  ngOnInit() {
    this.namedStorms = this.cwwedService.namedStorms;
    this.nsemList = this.cwwedService.nsemList;
  }

  public stormCoveredDataUrl(storm) {
    let foundNsem = _.find(this.nsemList, (nsem) => {
      return nsem.named_storm === storm.id;
    });
    return foundNsem ? foundNsem.thredds_url_covered_data : '';
  }
}
