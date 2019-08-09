import { Component, OnInit } from '@angular/core';
import { Router } from "@angular/router";
import { CwwedService } from "../cwwed.service";


@Component({
  selector: 'app-psa-export',
  templateUrl: './psa-export.component.html',
  styleUrls: ['./psa-export.component.css']
})
export class PsaExportComponent implements OnInit {

  constructor(
    private router: Router,
    private cwwedService: CwwedService,
  ) {}

  ngOnInit() {
    // redirect to login page if they're not logged in
    if (!this.cwwedService.user) {
      window.location.href = '/accounts/login?next=' +
        encodeURIComponent(`#${this.router.routerState.snapshot.url}`);
    }
  }

}
