import { Injectable } from '@angular/core';
import {environment} from "../environments/environment";

declare let gtag: Function;


@Injectable({
  providedIn: 'root'
})
export class GoogleAnalyticsService {

  constructor() { }

  public event(
    eventAction: string,
    eventCategory: string,
    eventLabel: string,
    eventValue: number = null )
  {
    if (environment.production) {
      gtag('event', eventAction, {
        event_category: eventCategory,
        event_label: eventLabel,
        event_value: eventValue
      });
    }
  }

  public psaBoxSelection(storm: string) {
    this.event('selection-tool', 'psa', storm);
  }

  public psaOpacity(storm: string, value: number) {
    this.event('opacity', 'psa', storm, value);
  }

  public psaBaseMap(storm: string) {
    this.event('base-map', 'psa', storm);
  }

  public psaDate(storm: string) {
    this.event('date', 'psa', storm);
  }

  public psaVariableToggle(storm: string) {
    this.event('variable-toggle', 'psa', storm);
  }

  public psaFullScreen(storm: string) {
    this.event('full-screen', 'psa', storm);
  }
}
