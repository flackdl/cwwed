import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { CoveredDataMainComponent } from './covered-data-main.component';

describe('CoveredDataMainComponent', () => {
  let component: CoveredDataMainComponent;
  let fixture: ComponentFixture<CoveredDataMainComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ CoveredDataMainComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(CoveredDataMainComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
