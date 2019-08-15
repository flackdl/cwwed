import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from "@angular/router";
import { CwwedService } from "../cwwed.service";
import { FormBuilder, FormControl, FormGroup } from "@angular/forms";
import * as _ from 'lodash';
import { tap } from "rxjs/operators";

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
  public psaVariables: any[] = [];
  public form: FormGroup;

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

    this._fetchDataAndBuildForm();
  }

  protected _fetchDataAndBuildForm() {

    // create initial form group
    this.form = this.fb.group({
      variables: new FormControl(),
    });

    // fetch psa variables
    this.cwwedService.fetchPSAVariables(this.storm.id).pipe(
      tap(
        (data: any[]) => {
          //this.isLoading = false;
          this.psaVariables = data;

          // create and populate variables form group
          let psaVariablesFormGroup = this.fb.group({});
          this.psaVariables.forEach((psaVariable) => {
            psaVariablesFormGroup.addControl(psaVariable.name, new FormControl(true));
          });
          this.form.setControl('variables', psaVariablesFormGroup);
        }),
    ).subscribe(
      (data) => {
        console.log(this.form);
      },
      (error) => {
        console.error(error);
        //this.isLoading = false;
      });
  }

}
