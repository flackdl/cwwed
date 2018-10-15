import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { CoastalActProjectsComponent } from './coastal-act-projects.component';

describe('CoastalActProjectsComponent', () => {
  let component: CoastalActProjectsComponent;
  let fixture: ComponentFixture<CoastalActProjectsComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ CoastalActProjectsComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(CoastalActProjectsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
