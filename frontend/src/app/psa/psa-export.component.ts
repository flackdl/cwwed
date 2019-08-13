import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from "@angular/router";
import { CwwedService } from "../cwwed.service";

import * as _ from 'lodash';


@Component({
  selector: 'app-psa-export',
  templateUrl: './psa-export.component.html',
  styleUrls: ['./psa-export.component.css']
})
export class PsaExportComponent implements OnInit {
  public storm: any;
  public extentCoords: [number, number, number, number];

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private cwwedService: CwwedService,
  ) {}

  ngOnInit() {

    // if they're not logged in, redirect to login page and then back here
    if (!this.cwwedService.user) {
      window.location.href = '/accounts/login?next=' +
        encodeURIComponent(`#${this.router.routerState.snapshot.url}`);
    }

    this.storm = _.find(this.cwwedService.namedStorms, (storm) => {
      return this.route.snapshot.params['id'] == storm.id;
    });
    if (!this.storm) {  // unknown storm - send them back
      this.router.navigate(['/post-storm-assessment']);
    }

    const extentCoords = this.route.snapshot.params['extentCoords'];
    if (extentCoords && extentCoords.length === 4) {
      this.extentCoords = this.route.snapshot.params['extentCoords'];
    }
  }

}
