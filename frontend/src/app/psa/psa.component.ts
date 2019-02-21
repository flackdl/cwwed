import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { ActivatedRoute } from "@angular/router";
import { HttpClient } from "@angular/common/http";
import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { CwwedService } from "../cwwed.service";
import { FormControl } from "@angular/forms";
import { debounceTime, tap } from 'rxjs/operators';
import Map from 'ol/Map.js';
import View from 'ol/View.js';
import {defaults as defaultControls, FullScreen} from 'ol/control.js';
import { platformModifierKeyOnly } from 'ol/events/condition.js';
import GeoJSON from 'ol/format/GeoJSON.js';
import { fromLonLat, toLonLat } from 'ol/proj.js';
import ExtentInteraction from 'ol/interaction/Extent.js';
import { Tile as TileLayer, Vector as VectorLayer } from 'ol/layer.js';
import { OSM, XYZ, Vector as VectorSource } from 'ol/source.js';
import { Fill, Style, Icon } from 'ol/style.js';
import Overlay from 'ol/Overlay.js';
import * as _ from 'lodash';
import * as Geocoder from "ol-geocoder/dist/ol-geocoder.js";
import { InjectionService } from "../../ngx-charts/common/tooltip/injection.service";

const seedrandom = require('seedrandom');
const hexToRgba = require("hex-to-rgba");


@Component({
  selector: 'app-psa',
  templateUrl: './psa.component.html',
  styleUrls: ['./psa.component.scss'],
})
export class PsaComponent implements OnInit {
  public S3_PSA_BUCKET_BASE_URL = 'https://s3.amazonaws.com/cwwed-static-assets-frontend/psa/';
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
  public isLoadingOverlayPopup = false;
  public map: Map;
  public nsemId: number;
  public namedStorms: any;
  public nsemList: any;
  public currentFeature: any;
  public extentCoords: Number[];
  public geojsonManifest: any;
  public currentConfidence: Number;
  public dateInputControl = new FormControl(0); // first date in the list
  public dataOpacityInput = new FormControl(.5);
  public waterDepthLayer: any;  // VectorLayer
  public windLayer: any;  // VectorLayer
  public mapLayerWaterDepthInput = new FormControl(true);
  public mapLayerWindInput = new FormControl(false);
  public mapLayerInput = new FormControl(this.MAP_LAYER_OSM_STANDARD);
  public popupOverlay: Overlay;
  public coordinateData: any[];
  @ViewChild('popup') popupEl: ElementRef;
  @ViewChild('map') mapEl: ElementRef;

  protected _extentInteraction: ExtentInteraction;

  constructor(
    private http: HttpClient,
    private route: ActivatedRoute,
    private cwwedService: CwwedService,
    private modalService: NgbModal,
    private chartTooltipInjectionService: InjectionService,
  ) {}

  ngOnInit() {
    // override chart tooltip container so it works in fullscreen
    this.chartTooltipInjectionService.setContainerElement(this.mapEl.nativeElement);

    this.nsemList = this.cwwedService.nsemList;
    this.namedStorms = this.cwwedService.namedStorms;

    this._listenForInputChanges();

    this._fetchDataAndBuildMap();

    this.route.params.subscribe((data) => {
      if (data.id) {
        this.nsemId = parseInt(data.id);
      }
    });
  }

  public openVideoModal(content, variable: string) {
    // attaching which dataset variable to display onto the template ref "content" (somewhat messy)
    content.variable = variable;
    this.modalService.open(content);
  }

  public getDateInputFormatted(dateIndex: number) {
    return this.geojsonManifest['mesh2d_waterdepth']['geojson'][dateIndex].date;
  }

  public getDateMin() {
    return this.getDateInputFormatted(0);
  }

  public getDateMax() {
    return this.getDateInputFormatted(this.geojsonManifest['mesh2d_waterdepth']['geojson'].length - 1);
  }

  public getDateInputMax() {
    return this.geojsonManifest['mesh2d_waterdepth']['geojson'].length - 1;
  }

  public closeOverlayPopup() {
    this.popupOverlay.setPosition(undefined);
  }

  public getDataUrl(format: string): string {
    return `${this.demoDataURL}.${format}`;
  }

  public animationVideoURL(variable: string) {
    return `${this.S3_PSA_BUCKET_BASE_URL}${this.geojsonManifest[variable]['video']}`;
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

  protected _listenForInputChanges() {

    // update map data opacity
    this.dataOpacityInput.valueChanges.subscribe(
      (data) => {
        this.waterDepthLayer.setStyle((feature) => {
          return this._waterDepthStyle(feature);
        });
        this.windLayer.setStyle((feature) => {
          return this._getWindStyle(feature);
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

    // listen for layer input changes
    this.mapLayerWaterDepthInput.valueChanges.pipe(
      tap(() => {
        this.isLoadingMap = true;
      })
    ).subscribe(
      (value) => {
        if (!value) {
          this.map.removeLayer(this.waterDepthLayer);
        } else {
          this.waterDepthLayer.setSource(this._getWaterDepthSource());
          this.map.addLayer(this.waterDepthLayer);
        }
      }
    );

    // listen for layer input changes
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
    this.dateInputControl.valueChanges.pipe(
      tap(() => {
        this.isLoadingMap = true;
      }),
      debounceTime(1000),
    ).subscribe((value) => {
      // update the map's layer's sources
      this.waterDepthLayer.setSource(this._getWaterDepthSource());
      this.windLayer.setSource(this._getWindSource());
    });
  }

  protected _getWaterDepthSource(): VectorSource {
    return new VectorSource({
      url: `${this.S3_PSA_BUCKET_BASE_URL}${this.geojsonManifest['mesh2d_waterdepth']['geojson'][this.dateInputControl.value].path}`,
      format: new GeoJSON()
    });
  }

  protected _getWindSource(): VectorSource {
    return new VectorSource({
      url: `${this.S3_PSA_BUCKET_BASE_URL}${this.geojsonManifest['wind']['geojson'][this.dateInputControl.value].path}`,
      format: new GeoJSON(),
    })
  }

  protected _getWindStyle(feature): Style {
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
        rotation: -feature.get('direction'),  // direction is in radians and rotates clockwise
        src: icon,
        opacity: this.dataOpacityInput.value,
      }),
    });
  }

  protected _fetchDataAndBuildMap() {

    this.http.get(`${this.S3_PSA_BUCKET_BASE_URL}manifest.json`).subscribe(
      (data) => {
        this.isLoading = false;
        this.geojsonManifest = data;
        // build the map
        this._buildMap();
      },
      (error) => {
        console.error(error);
        this.isLoading = false;
      }
    )
  }

  protected _waterDepthStyle(feature) {
    return new Style({
      fill: new Fill({
        color: hexToRgba(feature.get('fill'), this.dataOpacityInput.value),
      }),
    })
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
    this.waterDepthLayer = new VectorLayer({
      source: this._getWaterDepthSource(),
      style: (feature) => {
        return this._waterDepthStyle(feature);
      },
    });

    // create a vector layer with the wind data
    this.windLayer = new VectorLayer({
      source: this._getWindSource(),
      style: (feature) => {
        return this._getWindStyle(feature);
      },
    });

    this.map = new Map({
      controls: defaultControls().extend([
        new FullScreen(),
      ]),
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
        this.waterDepthLayer,
      ],
      target: this.mapEl.nativeElement,
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

    this._configureFeatureHover();

  }

  protected _getConfidenceValueAtPixel(pixel) {
    // TODO - generating random confidence using a consistent seed of the current pixel
    const rand = seedrandom(pixel.reduce(
      (p1, p2) => {
        return Math.round(p1) + Math.round(p2);
      }));
    const randValue = Math.round(rand() * 100);
    if (randValue < 50) {
      return randValue + 50;
    } else {
      return randValue;
    }
  }

  protected _configureFeatureHover() {

    // highlight current feature
    this.map.on('pointermove', (event) => {

      // don't show feature details if there's any popup overlay already present
      if (this.popupOverlay && this.popupOverlay.rendered.visible) {
        return;
      }

      this.currentConfidence = this._getConfidenceValueAtPixel(event.pixel);

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
    this.isLoadingOverlayPopup = true;
    this.coordinateData = null;

    // verify there is data at this location
    const features = this.map.getFeaturesAtPixel(event.pixel);
    if (!features) {
      this.closeOverlayPopup();
      this.isLoadingOverlayPopup = false;
      return;
    }

    this.popupOverlay.setPosition(event.coordinate);

    const latLon = toLonLat(event.coordinate).reverse();
    this.cwwedService.fetchPSACoordinateData(this.demoDataPath, latLon).subscribe(
      (data: any) => {
        this.isLoadingOverlayPopup = false;
        this.coordinateData = [
          {
            name: 'Water Depth',
            series: data.water_depth,
          },
          {
            name: 'Wind Speed',
            series: data.wind_speed,
          },
        ];
      },
      (error) => {
        console.error(error);
        this.isLoadingOverlayPopup = false;
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
