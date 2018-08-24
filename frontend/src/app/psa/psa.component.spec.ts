import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { PsaComponent } from './psa.component';

describe('PsaComponent', () => {
  let component: PsaComponent;
  let fixture: ComponentFixture<PsaComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ PsaComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(PsaComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
