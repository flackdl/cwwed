import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { PsaListComponent } from './psa-list.component';

describe('PsaListComponent', () => {
  let component: PsaListComponent;
  let fixture: ComponentFixture<PsaListComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ PsaListComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(PsaListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
