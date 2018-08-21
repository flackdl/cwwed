import { Component, OnInit, Input } from '@angular/core';

@Component({
  selector: 'app-covered-data-detail',
  templateUrl: './covered-data-detail.component.html',
  styleUrls: ['./covered-data-detail.component.css']
})
export class CoveredDataDetailComponent implements OnInit {
  @Input() data: any;

  constructor() { }

  ngOnInit() {
  }
}
