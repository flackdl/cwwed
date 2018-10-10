import { Component, OnInit } from '@angular/core';
import { CwwedService } from "../cwwed.service";

@Component({
  selector: 'app-coastal-act-projects',
  templateUrl: './coastal-act-projects.component.html',
  styleUrls: ['./coastal-act-projects.component.css']
})
export class CoastalActProjectsComponent implements OnInit {

  public isNavCollapsed = true;
  public coastalActProjects: any [];

  constructor(
    private cwwedService: CwwedService,
  ) {
  }

  ngOnInit() {
    this.coastalActProjects = this.cwwedService.coastalActProjects;
  }

  public toggleNavCollapse() {
    this.isNavCollapsed = !this.isNavCollapsed;
  }
}
