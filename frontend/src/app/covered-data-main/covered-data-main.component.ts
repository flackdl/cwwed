import { Component, OnInit } from '@angular/core';
import { CwwedService } from "../cwwed.service";

@Component({
  selector: 'app-covered-data-main',
  templateUrl: './covered-data-main.component.html',
  styleUrls: ['./covered-data-main.component.css']
})
export class CoveredDataMainComponent implements OnInit {
  public coveredDataList: any;
  public isNavCollapsed = true;

  constructor(
    private cwwedService: CwwedService,
  ) {}

  ngOnInit() {
    this.coveredDataList = this.cwwedService.coveredDataList;
  }

  public toggleNavCollapse() {
    this.isNavCollapsed = !this.isNavCollapsed;
  }
}
