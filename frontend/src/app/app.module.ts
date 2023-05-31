import { ReactiveFormsModule } from '@angular/forms';
import { BrowserModule } from '@angular/platform-browser';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { ErrorHandler, Injectable, NgModule } from '@angular/core';
import { NgbModule } from '@ng-bootstrap/ng-bootstrap';
import { HttpClientModule, HttpClientXsrfModule } from '@angular/common/http';
import { RouterModule, Routes } from "@angular/router";
import { NgxLoadingModule } from 'ngx-loading';
import { MomentModule } from 'ngx-moment';
import { ChartsModule } from "ng2-charts";
import { ToastrModule } from 'ngx-toastr';
import { GoogleAnalyticsService } from './google-analytics.service';


import * as Sentry from "@sentry/browser";


import { AppComponent } from './app.component';
import { CoveredDataDetailComponent } from './covered-data-detail/covered-data-detail.component';
import { CoveredDataMainComponent } from './covered-data-main/covered-data-main.component';
import { PsaComponent } from './psa/psa.component';
import { PageNotFoundComponent } from './page-not-found/page-not-found.component';
import { MainComponent } from './main/main.component';
import { CoastalActComponent } from './coastal-act/coastal-act.component';
import { CoastalActProjectsComponent } from './coastal-act-projects/coastal-act-projects.component';
import { CoastalActProjectsDetailComponent } from './coastal-act-projects-detail/coastal-act-projects-detail.component';
import { PsaExportComponent } from './psa/psa-export.component';
import { PsaListComponent } from './psa/psa-list.component';

Sentry.init({
  dsn: "https://80b326e2a7fa4e6abf9d3a9d19481c40@sentry.io/1281345",
});

@Injectable()
export class SentryErrorHandler implements ErrorHandler {
  constructor() {}
  handleError(error) {
    Sentry.captureException(error.originalError || error);
    console.error(error);
    throw error;
  }
}

const appRoutes: Routes = [
  { path: '',   redirectTo: '/coastal-act', pathMatch: 'full' },
  { path: 'cwwed', component: MainComponent },
  { path: 'coastal-act', component: CoastalActComponent },
  {
    path: 'coastal-act-projects',
    component: CoastalActProjectsComponent,
    children: [
      { path: '', component: CoastalActProjectsDetailComponent },
      { path: ':id', component: CoastalActProjectsDetailComponent },
    ]
  },
  {
    path: 'covered-data',
    component: CoveredDataMainComponent,
    children: [
      { path: '', component: CoveredDataDetailComponent },
      { path: ':id', component: CoveredDataDetailComponent },
    ]
  },
  { path: 'covered-data/:id', component: CoveredDataMainComponent },
  {
    path: 'post-storm-assessment',
    children: [
      { path: '', component: PsaListComponent },
      { path: ':name/:id', component: PsaComponent },
      { path: ':name/:id/export', component: PsaExportComponent },
    ],
  },
  { path: 'page-not-found', component: PageNotFoundComponent },
  { path: '**', component: PageNotFoundComponent }
];


@NgModule({
  declarations: [
    AppComponent,
    CoveredDataDetailComponent,
    CoveredDataMainComponent,
    PsaComponent,
    PageNotFoundComponent,
    MainComponent,
    CoastalActComponent,
    CoastalActProjectsComponent,
    CoastalActProjectsDetailComponent,
    PsaExportComponent,
    PsaListComponent,
  ],
  imports: [
    RouterModule.forRoot(
      appRoutes,
      {
        // TODO - this globally scrolls to top on navigation change but then prevents being able to add query params to the URL without scrolling...
        // https://github.com/angular/angular/issues/24547
        // scrollPositionRestoration: 'enabled',  // scroll to top on navigation change and remember position when going back
        useHash: true,
      }
    ),
    BrowserModule,
    BrowserAnimationsModule,
    NgbModule,
    HttpClientModule,
    HttpClientXsrfModule.withOptions({
      // specify django's csrf settings
      cookieName: 'csrftoken',
      headerName: 'X-CSRFToken',
    }),
    NgxLoadingModule,
    MomentModule,
    ReactiveFormsModule,
    ChartsModule,
    ToastrModule.forRoot(),
  ],
  entryComponents: [],
  providers: [
    { provide: ErrorHandler, useClass: SentryErrorHandler },
    GoogleAnalyticsService,
  ],
  bootstrap: [AppComponent]
})
export class AppModule {
  constructor() {
  }
}
