import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { NgbModule } from '@ng-bootstrap/ng-bootstrap';
import { HttpClientModule } from '@angular/common/http';
import { RouterModule, Routes} from "@angular/router";
import { NgxSpinnerModule } from 'ngx-spinner';

import { AppComponent } from './app.component';
import { CoveredDataDetailComponent } from './covered-data-detail/covered-data-detail.component';
import { CoveredDataMainComponent } from './covered-data-main/covered-data-main.component';
import { PsaComponent } from './psa/psa.component';
import { PageNotFoundComponent } from './page-not-found/page-not-found.component';

const appRoutes: Routes = [
  { path: '', component: CoveredDataMainComponent },
  { path: 'covered-data', component: CoveredDataMainComponent },
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
    PageNotFoundComponent
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
    NgbModule,
    HttpClientModule,
    NgxSpinnerModule,
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
