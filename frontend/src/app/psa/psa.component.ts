import { ActivatedRoute } from "@angular/router";
import { Component, OnInit } from '@angular/core';
import { CwwedService } from "../cwwed.service";

@Component({
  selector: 'app-psa',
  templateUrl: './psa.component.html',
  styleUrls: ['./psa.component.css']
})
export class PsaComponent implements OnInit {
  public nsemId: number;
  public namedStorms: any;
  public nsemList: any;

  constructor(
    private route: ActivatedRoute,
    private cwwedService: CwwedService,
  ) {}

  ngOnInit() {
    this.nsemList = this.cwwedService.nsemList;
    this.namedStorms = this.cwwedService.namedStorms;

    this.route.params.subscribe((data) => {
      if (data.id) {
        this.nsemId = parseInt(data.id);
      }
    });
  }

}
