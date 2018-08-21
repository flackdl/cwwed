import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { CoveredDataDetailComponent } from './covered-data.component';

describe('CoveredDataComponent', () => {
  let component: CoveredDataDetailComponent;
  let fixture: ComponentFixture<CoveredDataDetailComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ CoveredDataDetailComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(CoveredDataDetailComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
