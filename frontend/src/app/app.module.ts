import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { NgbModule } from '@ng-bootstrap/ng-bootstrap';
import { HttpClientModule } from '@angular/common/http';
import { RouterModule, Routes} from "@angular/router";

import { AppComponent } from './app.component';
import { CoveredDataDetailComponent } from './covered-data-detail/covered-data-detail.component';
import { CoveredDataMainComponent } from './covered-data-main/covered-data-main.component';

const appRoutes: Routes = [
  { path: 'covered-data/:id', component: CoveredDataMainComponent },
  { path: '**', component: CoveredDataMainComponent }
];


@NgModule({
  declarations: [
    AppComponent,
    CoveredDataDetailComponent,
    CoveredDataMainComponent
  ],
  imports: [
    RouterModule.forRoot(
      appRoutes,
      {
        //enableTracing: true, // <-- debugging purposes only
      }
    ),
    BrowserModule,
    NgbModule,
    HttpClientModule,
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
