import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { PsaOlComponent } from './psa-ol.component';

describe('PsaOlComponent', () => {
  let component: PsaOlComponent;
  let fixture: ComponentFixture<PsaOlComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ PsaOlComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(PsaOlComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
