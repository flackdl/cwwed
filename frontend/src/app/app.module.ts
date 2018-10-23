import { BrowserModule } from '@angular/platform-browser';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { NgModule} from '@angular/core';
import { NgbModule } from '@ng-bootstrap/ng-bootstrap';
import { HttpClientModule } from '@angular/common/http';
import { RouterModule, Routes} from "@angular/router";
import { NgxSpinnerModule } from 'ngx-spinner';

import { AppComponent } from './app.component';
import { CoveredDataDetailComponent } from './covered-data-detail/covered-data-detail.component';
import { CoveredDataMainComponent } from './covered-data-main/covered-data-main.component';
import { PsaComponent } from './psa/psa.component';
import { PageNotFoundComponent } from './page-not-found/page-not-found.component';
import { MainComponent } from './main/main.component';
import { CoastalActComponent } from './coastal-act/coastal-act.component';
import { CoastalActProjectsComponent } from './coastal-act-projects/coastal-act-projects.component';
import { CoastalActProjectsDetailComponent } from './coastal-act-projects-detail/coastal-act-projects-detail.component';

const appRoutes: Routes = [
  { path: '',   redirectTo: '/home', pathMatch: 'full' },
  { path: 'home', component: MainComponent },
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
  { path: 'post-storm-assessment', component: PsaComponent },
  { path: 'post-storm-assessment/:id', component: PsaComponent },
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
  ],
  imports: [
    RouterModule.forRoot(
      appRoutes,
      {
        //enableTracing: true, // <-- debugging purposes only
        useHash: true,
      }
    ),
    BrowserModule,
    BrowserAnimationsModule,
    NgbModule,
    HttpClientModule,
    NgxSpinnerModule,
  ],
  entryComponents: [],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule {
  constructor() {
  }
}
