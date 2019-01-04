import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { ActivatedRoute } from "@angular/router";
import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { CwwedService } from "../cwwed.service";
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
import { Fill, Style, Icon } from 'ol/style.js';
import Overlay from 'ol/Overlay.js';
import * as AWS from 'aws-sdk';
import * as _ from 'lodash';
import * as Geocoder from "ol-geocoder/dist/ol-geocoder.js";

const seedrandom = require('seedrandom');
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
  public demoDataURL = "/opendap/PSA_demo/Sandy_DBay/DBay-run_map.nc";
  public demoDataPath = "PSA_demo/Sandy_DBay/DBay-run_map.nc";
  public isLoading = true;
  public isLoadingMap = true;
  public isLoadingOverlay = false;
  public map: Map;
  public nsemId: number;
  public namedStorms: any;
  public nsemList: any;
  public currentFeature: any;
  public extentCoords: Number[];
  public contourSourcePaths: {
    [variable_name: string]: String[],
  } = {};
  public currentContour: String;
  public currentConfidence: Number;
  public contourDateInput = new FormControl(0); // first date in the list
  public mapDataOpacityInput = new FormControl(.5);
  public contourLayer: any;  // VectorLayer
  public windLayer: any;  // VectorLayer
  public mapLayerWaterDepthInput = new FormControl(true);
  public mapLayerWindInput = new FormControl(false);
  public mapLayerInput = new FormControl(this.MAP_LAYER_OSM_STANDARD);
  public popupOverlay: Overlay;
  public coordinateData: any[];
  @ViewChild('popup') popupEl: ElementRef;

  protected _extentInteraction: ExtentInteraction;

  constructor(
    private route: ActivatedRoute,
    private cwwedService: CwwedService,
    private modalService: NgbModal,
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

  public openModal(content) {
    this.modalService.open(content);
  }

  public getContourDateFormatted(dateIndex: number) {
    // extract the date from the file name
    if (this.contourSourcePaths['mesh2d_waterdepth']) {
      let currentContour = this.contourSourcePaths['mesh2d_waterdepth'][dateIndex];
      return currentContour ? currentContour.replace(/.*__(.*).json$/, "$1") : '';
    }
    return '';
  }

  public getDateMin() {
    return this.contourSourcePaths['mesh2d_waterdepth'] ?
      this.getContourDateFormatted(0) :
      null;
  }

  public getDateMax() {
    return this.contourSourcePaths['mesh2d_waterdepth'] ?
      this.getContourDateFormatted(this.contourSourcePaths['mesh2d_waterdepth'].length - 1) :
      null;
  }

  public getDateInputMax() {
    return this.contourSourcePaths['mesh2d_waterdepth'] ? this.contourSourcePaths['mesh2d_waterdepth'].length - 1 : 0;
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
    this.mapLayerWaterDepthInput.valueChanges.pipe(
      tap(() => {
        this.isLoadingMap = true;
      }),
    ).subscribe(
      (value) => {
        if (!value) {
          this.map.removeLayer(this.contourLayer);
        } else {
          this.currentContour = this.contourSourcePaths['mesh2d_waterdepth'][this.contourDateInput.value];
          this.contourLayer.setSource(this._getContourSource());
          this.map.addLayer(this.contourLayer);
        }
      }
    );

    this.mapLayerWindInput.valueChanges.pipe(
      tap(() => {
        this.isLoadingMap = true;
      }),
    ).subscribe(
      (value) => {
        if (!value) {
          this.map.removeLayer(this.windLayer);
        } else {
          this.map.addLayer(this.windLayer);
        }
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
      this.currentContour = this.contourSourcePaths['mesh2d_waterdepth'][value];
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
          }
        });

        if (Object.keys(this.contourSourcePaths).length > 0) {
          // sort each contour path set
          _.each(this.contourSourcePaths, (contours) => {
            contours.sort();
          });
          // use the first contour date as the initial
          this.currentContour = this.contourSourcePaths['mesh2d_waterdepth'][0];
          // build the map
          this._buildMap();
        } else {
          console.error('Error: No contours retrieved');
        }

        this.isLoading = false;
        console.log('finished loading initial data');
      }
    });
  }

  protected _contourStyle(feature) {
    return new Style({
      fill: new Fill({
        color: hexToRgba(feature.get('fill'), this.mapDataOpacityInput.value),
      }),
    })
  }

  public closePopup() {
    this.popupOverlay.setPosition(undefined);
  }

  public getDataUrl(format: string): string {
    return `${this.demoDataURL}.${format}`;
  }

  public currentAnimationURL() {
    // TODO - clean this up
    // https://s3.amazonaws.com/cwwed-static-assets-frontend/contours/mesh2d_waterdepth.mp4
    return `${this.S3_BUCKET_BASE_URL}contours/mesh2d_waterdepth.mp4`;
  }
  
  public xAxisTickFormatting(value: string) {
    const date = new Date(value);
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${month}/${day}`;
  }

  public hasExtentSelection(): boolean {
    return this._extentInteraction && this._extentInteraction.getExtent();
  }

  public resetExtentInteraction() {

    // reset extent selection and captured coordinates
    if (this._extentInteraction) {
      this.map.removeInteraction(this._extentInteraction);
    }
    this.extentCoords = null;

    // reconfigure extent
    this._configureMapExtentInteraction();
  }

  protected _buildMap() {

    const mapBoxToken = 'pk.eyJ1IjoiZmxhY2thdHRhY2siLCJhIjoiY2l6dGQ2MXp0MDBwMzJ3czM3NGU5NGRsMCJ9.5zKo4ZGEfJFG5ph6QlaDrA';

    // create an overlay to anchor the address specific popup to the map
    this.popupOverlay = new Overlay({
      element: this.popupEl.nativeElement,
      autoPan: true,
      autoPanAnimation: {
        duration: 250
      }
    });

    // create a vector layer with the contour data
    this.contourLayer = new VectorLayer({
      source: this._getContourSource(),
      style: (feature) => {
        return this._contourStyle(feature);
      },
    });

    // create a vector layer with the wind data
    this.windLayer = new VectorLayer({
      source: new VectorSource({
        url: `${this.S3_BUCKET_BASE_URL}wind.json`,
        format: new GeoJSON(),
      }),
      style: (feature) => {
        let icon;
        const speed = feature.get('speed') || 0; // m/s
        const knots = speed * 1.94384;
        // https://commons.wikimedia.org/wiki/Wind_speed
        if (_.inRange(knots, 0, 2)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_00.svg.png';
        } else if (_.inRange(knots, 2, 7)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_01.svg.png';
        } else if (_.inRange(knots, 7, 12)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_02.svg.png';
        } else if (_.inRange(knots, 12, 17)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_03.svg.png';
        } else if (_.inRange(knots, 17, 22)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_04.svg.png';
        } else if (_.inRange(knots, 22, 27)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_05.svg.png';
        } else if (_.inRange(knots, 27, 32)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_06.svg.png';
        } else if (_.inRange(knots, 32, 37)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_07.svg.png';
        } else if (_.inRange(knots, 37, 42)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_08.svg.png';
        } else if (_.inRange(knots, 42, 47)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_09.svg.png';
        } else if (_.inRange(knots, 47, 52)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_10.svg.png';
        } else if (_.inRange(knots, 52, 57)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_11.svg.png';
        } else if (_.inRange(knots, 57, 62)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_12.svg.png';
        } else if (_.inRange(knots, 62, 83)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_13.svg.png';
        } else if (_.inRange(knots, 83, 102)) {
          icon = '/assets/psa/50px-Symbol_wind_speed_14.svg.png';
        } else {
          icon = '/assets/psa/50px-Symbol_wind_speed_15.svg.png';
        }
        return new Style({
          image: new Icon({
            rotation: feature.get('direction'),
            src: icon,
            opacity: .5,
          }),
        })
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
      overlays: [this.popupOverlay],
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

    this.map.on('singleclick', (event) => {

      // configure graph overlay
      this._configureGraphOverlay(event);
    });

    this._configureMapExtentInteraction();

    // highlight current feature
    this.map.on('pointermove', (event) => {


      //
      // TODO - generating random confidence using a consistent seed of the current pixel
      //
      const rand = seedrandom(event.pixel.reduce(
        (p1, p2) => {
          return Math.round(p1) + Math.round(p2);
        }));
      const randValue = Math.round(rand() * 100);
      if (randValue < 50) {
        this.currentConfidence = randValue + 50;
      } else {
        this.currentConfidence = randValue;
      }


      const currentFeature = {};
      this.map.forEachFeatureAtPixel(event.pixel, (feature) => {
        if (feature.get('direction')) {
          currentFeature['direction'] = feature.get('direction');
        }
        if (feature.get('speed')) {
          currentFeature['speed'] = feature.get('speed');
        }
        if (feature.get('title')) { // TODO "title" should be correctly labeled as water depth
          currentFeature['title'] = feature.get('title');
        }
      });

      if (!Object.keys(currentFeature).length) {
        this.currentFeature = undefined;
        return;
      }
      this.currentFeature = currentFeature;
    });

  }

  protected _configureGraphOverlay(event) {
    this.isLoadingOverlay = true;
    this.coordinateData = null;

    // verify there is data at this location
    const features = this.map.getFeaturesAtPixel(event.pixel);
    if (!features) {
      this.isLoadingOverlay = false;
      return;
    }

    this.popupOverlay.setPosition(event.coordinate);

    const latLon = toLonLat(event.coordinate).reverse();
    this.cwwedService.fetchPSACoordinateData(this.demoDataPath, latLon).subscribe(
      (data: any) => {
        this.isLoadingOverlay = false;
        this.coordinateData = [
          {
            name: 'Water Depth',
            series: data.water_depth,
          }
        ];
      },
      (error) => {
        console.error(error);
        this.isLoadingOverlay = false;
      }
    );
  }

  protected _configureMapExtentInteraction() {

    // configure box extent selection
    this._extentInteraction = new ExtentInteraction({
      condition: platformModifierKeyOnly,
    });
    this.map.addInteraction(this._extentInteraction);
    this._extentInteraction.setActive(false);

    // enable geo box interaction by holding shift
    window.addEventListener('keydown', (event: any) => {
      if (event.keyCode == 16) {
        this._extentInteraction.setActive(true);
      }
    });

    // disable geo box interaction and capture extent box
    window.addEventListener('keyup', (event: any) => {
      if (event.keyCode == 16) {
        const extentCoords = this._extentInteraction.getExtent();
        if (extentCoords && extentCoords.length === 4) {
            this.extentCoords = toLonLat(<any>[extentCoords[0], extentCoords[1]]).concat(
              toLonLat(<any>[extentCoords[2], extentCoords[3]]));
        } else {
          this.extentCoords = null;
        }
        this._extentInteraction.setActive(false);
      }
    });
  }
}
