import { Component, OnInit } from '@angular/core';
import { forkJoin } from "rxjs";
import { CwwedService } from "./cwwed.service";
import { ToastrService } from 'ngx-toastr';
import {NavigationEnd, Router} from "@angular/router";
import { GoogleAnalyticsService } from './google-analytics.service';


@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent implements OnInit {
  public isLoading: boolean = true;
  public isNavCollapsed: boolean = false;

  constructor(
    private cwwedService: CwwedService,
    private toastr: ToastrService,
    private router: Router,
    private googleAnalyticsService: GoogleAnalyticsService,
  ) {

    this.router.events.subscribe((event) => {
      // track route change in google analytics
      if(event instanceof NavigationEnd){
        this.googleAnalyticsService.url(event.urlAfterRedirects);
      }
    });
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
    forkJoin([
      this.cwwedService.fetchCoveredData(),
      this.cwwedService.fetchNamedStorms(),
      this.cwwedService.fetchNSEMPerStorm(),
      this.cwwedService.fetchCoastalActProjects(),
      this.cwwedService.fetchUser(),
    ]).subscribe(
      () => {
        this.isLoading = false;
      },
      (error) => {
        console.log(error);
        this.toastr.error('An unknown error occurred loading initial data');
        this.isLoading = false;
      });
  }
}
