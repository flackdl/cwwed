import { ActivatedRoute } from "@angular/router";
import { Component, OnInit } from '@angular/core';
import { CwwedService } from "../cwwed.service";
import { HttpParams } from "@angular/common/http";
import { debounceTime, tap } from 'rxjs/operators';
import * as AWS from 'aws-sdk';

import Map from 'ol/Map.js';
import View from 'ol/View.js';
import { platformModifierKeyOnly } from 'ol/events/condition.js';
import GeoJSON from 'ol/format/GeoJSON.js';
import { fromLonLat, toLonLat } from 'ol/proj.js';
import ExtentInteraction from 'ol/interaction/Extent.js';
import { Tile as TileLayer, Vector as VectorLayer } from 'ol/layer.js';
import { OSM, Vector as VectorSource } from 'ol/source.js';
import { Fill, Style } from 'ol/style.js';
import { FormControl } from "@angular/forms";

@Component({
  selector: 'app-psa',
  templateUrl: './psa.component.html',
  styleUrls: ['./psa.component.scss'],
})
export class PsaComponent implements OnInit {
  public demoDataURL = "https://dev.cwwed-staging.com/thredds/dodsC/cwwed/delaware.nc.html";
  public demoDataPath = "/media/bucket/cwwed/THREDDS/delaware.nc";
  public isLoading = true;
  public map;
  public nsemId: number;
  public namedStorms: any;
  public nsemList: any;
  public currentFeature: any;
  public extentCoords: Number[];
  public contourSources: String[] = [];
  public currentContour: String;
  public contourDateInput = new FormControl(0);
  public contourLayer: any;  // VectorLayer

  constructor(
    private route: ActivatedRoute,
    private cwwedService: CwwedService,
  ) {}

  ngOnInit() {
    this.nsemList = this.cwwedService.nsemList;
    this.namedStorms = this.cwwedService.namedStorms;

    this.contourDateInput.valueChanges.pipe(
      tap(() => {
        this.isLoading = true;
      }),
      debounceTime(1000),
    ).subscribe((value) => {
      // update the map's contour source
      this.currentContour = this.contourSources[value];
      this.contourLayer.setSource(this._getContourSource());

      // TODO - wait until new vector source is fully loaded
      this.isLoading = false;
    });

    this._fetchContourDataAndBuildMap();

    this.route.params.subscribe((data) => {
      if (data.id) {
        this.nsemId = parseInt(data.id);
      }
    });
  }

  public getCurrentContourFormatted() {
    // TODO - replace this poor solution and redo overall data structures (i.e contour file names)
    return this.currentContour.replace(/.*\//, '').replace(/\..*$/, '');
  }

  protected _getContourSource(): VectorSource {
    const bucketPrefix = 'https://s3.amazonaws.com/cwwed-static-assets-frontend/';

    return new VectorSource({
      url: `${bucketPrefix}${this.currentContour}`,
      format: new GeoJSON()
    });
  }

  protected _fetchContourDataAndBuildMap() {

    const S3 = new AWS.S3();
    let params = {
      Bucket: 'cwwed-static-assets-frontend',
      Prefix: 'contours/',
      Delimiter: '/',
    };

    // TODO handle paging
    // https://github.com/awslabs/aws-js-s3-explorer/blob/master/index.html

    S3.makeUnauthenticatedRequest('listObjectsV2', params, (error, data) => {
      if (error) {
        console.log('error', error);
      } else {

        // retrieve and sort the objects (dated)
        this.contourSources = data.Contents.map((value) => {
          return value.Key;
        }).sort();

        if (this.contourSources.length > 0) {
          // use the first contour date
          this.currentContour = this.contourSources[0];
          this._buildMap();
        } else {
          console.log('Error: No contours retrieved');
        }
      }
    });
  }

  protected _getContourStyle(feature) {
    return new Style({
      fill: new Fill({
        color: feature.get('fill')
      })
    })
  };

  protected _buildMap() {

    this.contourLayer = new VectorLayer({
      source: this._getContourSource(),
      style: (feature) => {
        return this._getContourStyle(feature);
      },
    });

    this.map = new Map({
      layers: [
        new TileLayer({
          source: new OSM()
        }),
        this.contourLayer,
      ],
      target: 'map',
      view: new View({
        center: fromLonLat(<any>[-75.249730, 39.153332]),
        zoom: 8,
      })
    });

    // flag we're finished loading the map
    this.map.on('rendercomplete', () => {
      this.isLoading = false;
    });

    const extent = new ExtentInteraction({
      condition: platformModifierKeyOnly,
    });

    this.map.addInteraction(extent);

    extent.setActive(false);

    // enable interaction by holding shift
    window.addEventListener('keydown', (event: any) => {
      if (event.keyCode == 16) {
        this.extentCoords = [];
        extent.setActive(true);
      }
    });

    // disable interaction and catpure extent box
    window.addEventListener('keyup', (event: any) => {
      if (event.keyCode == 16) {
        const extentCoords = extent.getExtent();
        if (extentCoords && extentCoords.length === 4) {
            this.extentCoords = toLonLat(<any>[extentCoords[0], extentCoords[1]]).concat(
              toLonLat(<any>[extentCoords[2], extentCoords[3]]));
        } else {
          this.extentCoords = null;
        }
        extent.setActive(false);
      }
    });

    // highlight current feature
    this.map.on('pointermove', (event) => {
      const features = this.map.getFeaturesAtPixel(event.pixel);
      if (!features) {
        this.currentFeature = undefined;
        return;
      }
      this.currentFeature = features[0].getProperties();
    });

  }

  public filteredDownloadURL() {
    const params = {
      path: this.demoDataPath,
    };

    if (this.extentCoords) {
      params['extent'] = this.extentCoords;
    }

    const httpParams = new HttpParams({fromObject: params});

    return `/psa-filter/?${httpParams.toString()}`;
  }

}
