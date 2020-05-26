import { Injectable } from '@angular/core';
import {environment} from "../environments/environment";

declare let gtag: Function;
const GA_CODE = 'UA-163877408-1';


@Injectable({
  providedIn: 'root'
})
export class GoogleAnalyticsService {

  constructor() { }

  public url(url: string) {
    if (this._shouldTrack()) {
      gtag('config', GA_CODE,
        {
          'page_path': url,
        }
      );
    }
  }

  public event(
    eventAction: string,
    eventCategory: string,
    eventLabel?: string,
    eventValue?: number
  )
  {
    if (this._shouldTrack()) {
      gtag('event', eventAction, {
        event_category: eventCategory,
        event_label: eventLabel,
        event_value: eventValue
      });
    }
  }

  public psaBoxSelection(storm: string) {
    this.event('psa-selection-tool', storm);
  }

  public psaOpacity(storm: string, opacity: string) {
    this.event('psa-opacity', storm, opacity);
  }

  public psaBaseMap(storm: string, mapName: string) {
    this.event('psa-base-map', storm, mapName);
  }

  public psaDate(storm: string) {
    this.event('psa-date', storm);
  }

  public psaVariableToggle(storm: string) {
    this.event('psa-variable-toggle', storm);
  }

  public psaFullScreen(storm: string) {
    this.event('psa-full-screen', storm);
  }

  public psaExport(storm: string, format: string) {
    this.event('psa-export', storm, format);
  }

  protected _shouldTrack (): boolean {
    return environment.production;
  }
}
