import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from "@angular/router";
import { CwwedService } from "../cwwed.service";
import { FormBuilder, FormGroup } from "@angular/forms";
import WKT from 'ol/format/WKT.js';
import { fromExtent } from 'ol/geom/Polygon.js';
import { timer } from 'rxjs';
import * as _ from 'lodash';

@Component({
  selector: 'app-psa-export',
  templateUrl: './psa-export.component.html',
  styleUrls: ['./psa-export.component.css']
})
export class PsaExportComponent implements OnInit {
  public FORMAT_TYPES = ["netcdf", "shapefile"];
  public storm: any;
  public format: string;
  public extentCoords: [number, number, number, number];
  public form: FormGroup;
  public psaUserExport: any;
  public isLoading = false;
  public isComplete = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private cwwedService: CwwedService,
    private fb: FormBuilder,
  ) {}

  ngOnInit() {

    // if they're not logged in, redirect to login page and then back here
    if (!this.cwwedService.user) {
      window.location.href = '/accounts/login?next=' +
        encodeURIComponent(`#${this.router.routerState.snapshot.url}`);
    }

    // storm
    this.storm = _.find(this.cwwedService.namedStorms, (storm) => {
      return this.route.snapshot.params['id'] == storm.id;
    });

    // extent coordinates
    const extentCoords = this.route.snapshot.queryParams['extent'];
    if (extentCoords && extentCoords.length === 4) {
      this.extentCoords = extentCoords;
    }

    // export format type
    if (_.includes(this.FORMAT_TYPES, this.route.snapshot.queryParams['format'])) {
      this.format = this.route.snapshot.queryParams['format'];
    }

    // unknown data - send them back
    if (!this.storm || !this.extentCoords || !this.format) {
      this.router.navigate(['/post-storm-assessment']);
    }

    // create initial form group
    this.form = this.fb.group({
    });
  }

  public getUser() {
    return this.cwwedService.user;
  }

  public submit() {
    const wkt = new WKT();
    const bbox_polygon = fromExtent(this.extentCoords);
    const bbox_wkt = wkt.writeGeometry(bbox_polygon);
    this.cwwedService.createPsaUserExport(this.storm.id, bbox_wkt, this.format).subscribe(
      (data: any) => {
        this.isLoading = true;
        this._checkExport(0, data.id);
      },
      (error) => {
        console.error(error);
      }
    );
  }

  protected _checkExport(delay: number, id: number) {
    timer(delay).subscribe(
      (data) => {
        this.cwwedService.fetchPSAUserExport(id).subscribe(
          (data: any) => {
            if (data.date_completed) {
              this.psaUserExport = data;
              this.isComplete = true;
              this.isLoading = false;
            } else {
              this._checkExport(1000, id);
            }
          }
        )
      }
    );

  }
}
