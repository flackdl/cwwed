import { TestBed, inject } from '@angular/core/testing';

import { CwwedService } from './cwwed-service.service';

describe('CwwedService', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [CwwedService]
    });
  });

  it('should be created', inject([CwwedService], (service: CwwedService) => {
    expect(service).toBeTruthy();
  }));
});
