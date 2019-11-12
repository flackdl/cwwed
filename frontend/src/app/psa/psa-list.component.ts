import { Component, OnInit } from '@angular/core';
import { CwwedService } from "../cwwed.service";

@Component({
  selector: 'app-psa-list',
  templateUrl: './psa-list.component.html',
  styleUrls: ['./psa-list.component.css']
})
export class PsaListComponent implements OnInit {

  public namedStorms: any[];

  constructor(
    private cwwedService: CwwedService,
  ) {}

  ngOnInit() {
    this.namedStorms = this.cwwedService.namedStorms.filter((storm) => {
      return this.cwwedService.nsemPsaList.find((psa) => {
        return psa.named_storm === storm.id;
      });
    });
  }

}
