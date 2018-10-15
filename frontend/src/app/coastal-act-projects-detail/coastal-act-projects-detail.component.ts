import { ActivatedRoute } from "@angular/router";
import { Component, OnInit } from '@angular/core';
import { CwwedService } from "../cwwed.service";
import * as _ from 'lodash';

@Component({
  selector: 'app-coastal-act-projects-detail',
  templateUrl: './coastal-act-projects-detail.component.html',
  styleUrls: ['./coastal-act-projects-detail.component.css']
})
export class CoastalActProjectsDetailComponent implements OnInit {
  public project: any;

  constructor(
    private route: ActivatedRoute,
    private cwwedService: CwwedService,
  ) { }

  ngOnInit() {

    this.route.params.subscribe((data) => {
      this.project = _.find(this.cwwedService.coastalActProjects, (project) => {
        return project.id == data.id;
      });
    });
  }
}
