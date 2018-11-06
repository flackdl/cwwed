import { ActivatedRoute } from "@angular/router";
import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { CwwedService } from "../cwwed.service";
import { HttpParams } from "@angular/common/http";
import { FormControl } from "@angular/forms";
import { debounceTime, tap } from 'rxjs/operators';
import Map from 'ol/Map.js';
import View from 'ol/View.js';
import { platformModifierKeyOnly } from 'ol/events/condition.js';
import GeoJSON from 'ol/format/GeoJSON.js';
import { fromLonLat, toLonLat } from 'ol/proj.js';
import ExtentInteraction from 'ol/interaction/Extent.js';
import { Tile as TileLayer, Vector as VectorLayer } from 'ol/layer.js';
import { OSM, XYZ, Vector as VectorSource } from 'ol/source.js';
import { Fill, Style } from 'ol/style.js';
import * as AWS from 'aws-sdk';
import * as _ from 'lodash';
import * as Geocoder from "ol-geocoder/dist/ol-geocoder.js";

const hexToRgba = require("hex-to-rgba");


@Component({
  selector: 'app-psa',
  templateUrl: './psa.component.html',
  styleUrls: ['./psa.component.scss'],
})
export class PsaComponent implements OnInit {
  public S3_BUCKET_BASE_URL = 'https://s3.amazonaws.com/cwwed-static-assets-frontend/';
  public MAP_LAYER_OSM_STANDARD = 'osm-standard';
  public MAP_LAYER_STAMEN_TONER = 'stamen-toner';
  public MAP_LAYER_MAPBOX_STREETS = 'mapbox-streets';
  public MAP_LAYER_MAPBOX_SATELLITE = 'mapbox-satellite';
  public MAP_LAYER_MAPBOX_LIGHT = 'mapbox-light';

  public mapLayerOptions = [
    { name: 'OpenStreetMap', value: this.MAP_LAYER_OSM_STANDARD },
    { name: 'MapBox Streets', value: this.MAP_LAYER_MAPBOX_STREETS },
    { name: 'MapBox Light', value: this.MAP_LAYER_MAPBOX_LIGHT },
    { name: 'MapBox Satellite', value: this.MAP_LAYER_MAPBOX_SATELLITE },
    { name: 'Stamen Toner', value: this.MAP_LAYER_STAMEN_TONER },
  ];
  public isMapControlsCollapsed = true;
  public demoDataURL = "https://dev.cwwed-staging.com/thredds/dodsC/cwwed/delaware.nc.html";
  public demoDataPath = "/media/bucket/cwwed/THREDDS/delaware.nc";
  public isLoading = true;
  public isLoadingMap = true;
  public map: any; // ol.Map
  public nsemId: number;
  public namedStorms: any;
  public nsemList: any;
  public currentFeature: any;
  public extentCoords: Number[];
  public contourSourcePaths: {
    [variable_name: string]: String[],
  } = {};
  public currentContour: String;
  public contourDateInput = new FormControl(0);
  public mapDataOpacityInput = new FormControl(.5);
  public contourLayer: any;  // VectorLayer
  public contourVariableInput = new FormControl('mesh2d_waterdepth');
  public currentVariable: string = 'mesh2d_waterdepth';
  public mapLayerInput = new FormControl(this.MAP_LAYER_OSM_STANDARD);
  @ViewChild('animation') animationSource: ElementRef;

  constructor(
    private route: ActivatedRoute,
    private cwwedService: CwwedService,
  ) {}

  ngOnInit() {
    this.nsemList = this.cwwedService.nsemList;
    this.namedStorms = this.cwwedService.namedStorms;

    this._listenForInputChanges();

    this._fetchContourDataAndBuildMap();

    this.route.params.subscribe((data) => {
      if (data.id) {
        this.nsemId = parseInt(data.id);
      }
    });
  }

  public getCurrentContourDateFormatted() {
    // extract the date from the file name
    if (this.contourSourcePaths[this.currentVariable]) {
      let currentContour = this.contourSourcePaths[this.currentVariable][this.contourDateInput.value];
      return currentContour ? currentContour.replace(/.*__(.*).json$/, "$1") : '';
    }
    return '';
  }

  public getDateInputMax() {
    return this.contourSourcePaths[this.currentVariable] ? this.contourSourcePaths[this.currentVariable].length - 1 : 0;
  }

  protected _listenForInputChanges() {

    // update map data opacity
    this.mapDataOpacityInput.valueChanges.subscribe(
      (data) => {
        this.contourLayer.setStyle((feature) => {
          return this._contourStyle(feature);
        });
      }
    );

    // update map tile layer
    this.mapLayerInput.valueChanges.subscribe(
      (value) => {
        this.map.getLayers().getArray().forEach((layer) => {
          const mapName = layer.get('mapName');
          if (mapName) {
            layer.setVisible(mapName === value);
          }
        });
      }
    );

    // listen for variable input changes
    this.contourVariableInput.valueChanges.pipe(
      tap(() => {
        this.isLoadingMap = true;
      }),
    ).subscribe(
      (value) => {
        this.currentVariable = value;
        this.currentContour = this.contourSourcePaths[this.currentVariable][this.contourDateInput.value];
        this.contourLayer.setSource(this._getContourSource());
        this.animationSource.nativeElement.load();
      }
    );

    // listen for date input changes
    this.contourDateInput.valueChanges.pipe(
      tap(() => {
        this.isLoadingMap = true;
      }),
      debounceTime(1000),
    ).subscribe((value) => {
      // update the map's contour source
      this.currentContour = this.contourSourcePaths[this.currentVariable][value];
      this.contourLayer.setSource(this._getContourSource());
    });
  }

  protected _getContourSource(): VectorSource {

    return new VectorSource({
      url: `${this.S3_BUCKET_BASE_URL}${this.currentContour}`,
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
        console.error('error', error);
        this.isLoading = false;
      } else {

        // retrieve and sort the objects (dated)
        data.Contents.forEach((value: any) => {

          // extract variable and file name from name, i.e "mesh2d_waterdepth__2012-10-22T07:00:00.json"
          let path: string = value.Key;
          let fileName: string = path.replace(data.Prefix, '');

          let contourVariable: string = fileName.replace(/(.*)__.*$/, '$1');
          let contourMatch = /.*.json$/.test(fileName);

          let animationMatch = /.*.mp4$/.test(fileName);
          let animationVariable: string = fileName.replace(/(.*).*$/, '$1');

          if (contourMatch && contourVariable) {
            if (!this.contourSourcePaths[contourVariable]) {
              this.contourSourcePaths[contourVariable] = [];
            }
            this.contourSourcePaths[contourVariable].push(path);
          } else if (animationMatch && animationVariable) {
            // TODO
            console.log(value);
          }
        });

        if (Object.keys(this.contourSourcePaths).length > 0) {
          // sort each contour path set
          _.each(this.contourSourcePaths, (contours) => {
            contours.sort();
          });
          // use the first contour date as the initial
          this.currentContour = this.contourSourcePaths[this.currentVariable][0];
          // build the map
          this._buildMap();
        } else {
          console.error('Error: No contours retrieved');
        }

        this.isLoading = false;
        console.log('finished loading (got s3 objects)');
      }
    });
  }

  protected _contourStyle (feature) {
    return new Style({
      fill: new Fill({
        color: hexToRgba(feature.get('fill'), this.mapDataOpacityInput.value),
      }),
    })
  }

  protected _buildMap() {

    const mapBoxToken = 'pk.eyJ1IjoiZmxhY2thdHRhY2siLCJhIjoiY2l6dGQ2MXp0MDBwMzJ3czM3NGU5NGRsMCJ9.5zKo4ZGEfJFG5ph6QlaDrA';

    this.contourLayer = new VectorLayer({
      source: this._getContourSource(),
      style: (feature) => {
        return this._contourStyle(feature);
      },
    });

    this.map = new Map({
      layers: [
        new TileLayer({
          mapName: this.MAP_LAYER_OSM_STANDARD,
          source: new OSM(),
        }),
        new TileLayer({
          mapName: this.MAP_LAYER_MAPBOX_LIGHT,
          visible: false,
          source: new XYZ({
            url: `https://api.mapbox.com/styles/v1/mapbox/light-v9/tiles/256/{z}/{x}/{y}?access_token=${mapBoxToken}`,
          })
        }),
        new TileLayer({
          mapName: this.MAP_LAYER_MAPBOX_SATELLITE,
          visible: false,
          source: new XYZ({
            url: `https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v9/tiles/256/{z}/{x}/{y}?access_token=${mapBoxToken}`,
          })
        }),
        new TileLayer({
          mapName: this.MAP_LAYER_MAPBOX_STREETS,
          visible: false,
          source: new XYZ({
            url: `https://api.mapbox.com/styles/v1/mapbox/streets-v10/tiles/256/{z}/{x}/{y}?access_token=${mapBoxToken}`,
          })
        }),
        new TileLayer({
          mapName: this.MAP_LAYER_STAMEN_TONER,
          visible: false,
          source: new XYZ({
            url: 'http://a.tile.stamen.com/toner/{z}/{x}/{y}.png',
          })
        }),
        this.contourLayer,
      ],
      target: 'map',
      view: new View({
        center: fromLonLat(<any>[-75.249730, 39.153332]),
        zoom: 8,
      })
    });

    // instantiate geocoder
    const geocoder = new Geocoder('nominatim', {
      provider: 'osm',
      lang: 'en-US',
      placeholder: 'Search ...',
      targetType: 'glass-button',
      limit: 5,
      keepOpen: true,
      autoComplete: true,
      countrycodes: 'us',
    });
    this.map.addControl(geocoder);

    // flag we're finished loading the map
    this.map.on('rendercomplete', () => {
      this.isLoadingMap = false;
    });

    // close map controls on single click
    this.map.on('singleclick', () => {
      this.isMapControlsCollapsed = true;
    });

    // configure box extent selection
    const extent = new ExtentInteraction({
      condition: platformModifierKeyOnly,
    });
    this.map.addInteraction(extent);
    extent.setActive(false);

    // enable geo box interaction by holding shift
    window.addEventListener('keydown', (event: any) => {
      if (event.keyCode == 16) {
        extent.setActive(true);
      }
    });

    // disable geo box interaction and catpure extent box
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

  public currentAnimationURL() {
    // TODO - clean this up
    // https://s3.amazonaws.com/cwwed-static-assets-frontend/contours/mesh2d_waterdepth.mp4
    return `${this.S3_BUCKET_BASE_URL}contours/${this.currentVariable}.mp4`;
  }
}
