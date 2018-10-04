import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { CoastalActComponent } from './coastal-act.component';

describe('CoastalActComponent', () => {
  let component: CoastalActComponent;
  let fixture: ComponentFixture<CoastalActComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ CoastalActComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(CoastalActComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
