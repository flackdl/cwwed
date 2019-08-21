import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { PsaExportComponent } from './psa-export.component';

describe('PsaExportComponent', () => {
  let component: PsaExportComponent;
  let fixture: ComponentFixture<PsaExportComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ PsaExportComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(PsaExportComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
