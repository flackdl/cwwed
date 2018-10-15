import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { CoastalActProjectsDetailComponent } from './coastal-act-projects-detail.component';

describe('CoastalActProjectsDetailComponent', () => {
  let component: CoastalActProjectsDetailComponent;
  let fixture: ComponentFixture<CoastalActProjectsDetailComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ CoastalActProjectsDetailComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(CoastalActProjectsDetailComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
