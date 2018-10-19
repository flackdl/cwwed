import { NgxSpinnerService } from "ngx-spinner";
import { Component, OnInit } from '@angular/core';
import { forkJoin } from "rxjs";
import { CwwedService } from "./cwwed.service";


@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent implements OnInit {
  public isLoaded: boolean = false;
  public isNavCollapsed: boolean = false;

  constructor(
    private cwwedService: CwwedService,
    private spinner: NgxSpinnerService,
  ) {
  }

  public navCollapse() {
    this.isNavCollapsed = false;
  }

  public toggleNavCollapse() {
    this.isNavCollapsed = !this.isNavCollapsed;
  }

  public isLoggedIn(): boolean {
    return !!this.cwwedService.user;
  }

  public userName(): string {
    return this.isLoggedIn() ? this.cwwedService.user.username : '';
  }

  ngOnInit() {
    // show loading animation until the core data has been loaded
    this.spinner.show();
    forkJoin(
      this.cwwedService.fetchCoveredData(),
      this.cwwedService.fetchNamedStorms(),
      this.cwwedService.fetchNSEMPerStorm(),
      this.cwwedService.fetchCoastalActProjects(),
      this.cwwedService.fetchUser(),
    ).subscribe(
      () => {
        this.isLoaded = true;
        this.spinner.hide();
      },
      (error) => {
        console.log(error);
      });
  }
}
